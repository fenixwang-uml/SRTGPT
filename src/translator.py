"""
翻译模块：支持 DeepL API 和本地 Ollama 两种后端
"""
import time
import re
import urllib.request
import urllib.parse
import json
from typing import List

# 每批最多传给 DeepL 的字幕条数（API 单次请求上限为 50 条）
BATCH_SIZE = 50


class DeepLTranslator:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        # Free 版和 Pro 版使用不同的域名
        if self.api_key.endswith(':fx'):
            self.base_url = "https://api-free.deepl.com/v2"
        else:
            self.base_url = "https://api.deepl.com/v2"

    def _request(self, texts: List[str]) -> List[str]:
        """
        向 DeepL API 发送多条文本，利用原生多 text 参数支持。
        一次请求返回与输入等长的译文列表，无需拼接分隔符。
        """
        url = f"{self.base_url}/translate"

        # DeepL 支持同一参数名重复传递多个值
        params = [("source_lang", "JA"), ("target_lang", "ZH")]
        params += [("text", t) for t in texts]

        data = urllib.parse.urlencode(params).encode('utf-8')
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        req.add_header('Authorization', f'DeepL-Auth-Key {self.api_key}')

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        return [t['text'] for t in result['translations']]

    def translate_blocks(
        self,
        texts: List[str],
        progress_callback=None
    ) -> List[str]:
        """
        翻译字幕文本列表。
        每批直接传多个 text 参数给 DeepL，返回等长译文列表。
        progress_callback(done, total) 用于更新进度条。
        """
        results = []
        total = len(texts)

        for i in range(0, total, BATCH_SIZE):
            batch = texts[i: i + BATCH_SIZE]

            retries = 0
            while True:
                try:
                    translated = self._request(batch)
                    # 数量校验：异常时保留原文
                    if len(translated) != len(batch):
                        translated = batch
                    break
                except Exception:
                    retries += 1
                    if retries >= 5:
                        translated = batch   # 重试耗尽：保留原文
                        break
                    time.sleep(2 ** retries)

            results.extend(translated)

            if progress_callback:
                progress_callback(len(results), total)

            if i + BATCH_SIZE < total:
                time.sleep(0.3)

        return results

    def check_usage(self):
        """查询当月 API 用量"""
        url = f"{self.base_url}/usage"
        req = urllib.request.Request(url, method='GET')
        req.add_header('Authorization', f'DeepL-Auth-Key {self.api_key}')
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())


class OllamaTranslator:
    """本地 Ollama 翻译后端，针对 4070 Ti (12GB) 优化"""

    SYSTEM_PROMPT = (
        "你是一名专业的影视字幕翻译，负责将日文字幕翻译为简体中文。"
        "要求：\n"
        "1. 只输出译文，不添加任何解释、注释或多余标点\n"
        "2. 保持原文的换行格式\n"
        "3. 人名、地名等专有名词音译或保留原文\n"
        "4. 语言自然流畅，符合中文字幕习惯"
    )

    # 针对 4070 Ti 的推理参数
    # 字幕场景特点：输入短（10-30字）、输出短、需要稳定不发挥
    GPU_OPTIONS = {
        "num_gpu":       99,     # 所有层全部加载到 GPU，不留给 CPU
        "num_ctx":       512,    # 字幕极短，512 足够，省显存给 KV cache
        "num_batch":     512,    # prompt 并行处理批大小，越大越快
        "num_thread":    4,      # CPU 线程（仅处理非 GPU 部分，4 够用）
        "temperature":   0.1,    # 低随机性，翻译稳定不乱发挥
        "repeat_penalty": 1.1,   # 避免译文出现重复短语
        "top_k":         20,     # 缩小采样范围，配合低温度加速
        "top_p":         0.9,
    }

    def __init__(self, model: str = "qwen2.5:14b"):
        self.model = model
        self.url = "http://localhost:11434/api/chat"

    def _translate_one(self, text: str) -> str:
        payload = {
            "model":   self.model,
            "stream":  False,
            "options": self.GPU_OPTIONS,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user",   "content": text},
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req  = urllib.request.Request(self.url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        return result["message"]["content"].strip()

    def benchmark(self, samples: List[str], n: int = 3) -> tuple:
        """
        用真实字幕测速，返回 (单条均时, 修正系数)。
        第一轮：context 为空（冷启动）
        第二轮：context 填满（稳定状态）
        修正系数 = 第二轮均时 / 第一轮均时，反映上下文窗口的实际开销。
        """
        test_texts = [t for t in samples if t.strip()][:n]
        if not test_texts:
            return 3.0, 1.0

        # 第一轮：无上下文
        start = time.time()
        try:
            self._translate_batch(test_texts, context=[])
        except Exception:
            pass
        secs_cold = (time.time() - start) / len(test_texts)

        # 第二轮：填满上下文窗口
        full_context = [(t, t) for t in test_texts * 2][-self.CONTEXT_SIZE:]
        start = time.time()
        try:
            self._translate_batch(test_texts, context=full_context)
        except Exception:
            pass
        secs_warm = (time.time() - start) / len(test_texts)

        # 修正系数：至少为 1.0，避免第二轮因缓存反而更快导致系数 < 1
        factor = max(secs_warm / secs_cold, 1.0) if secs_cold > 0 else 1.0

        return secs_cold, factor

    # 每批打包翻译的字幕条数
    BATCH_SIZE = 8
    # 滑动窗口：带入前几条已译结果作为上下文
    CONTEXT_SIZE = 5

    def _translate_batch(self, texts: List[str], context: List[tuple]) -> List[str]:
        """
        批量翻译一组字幕，同时携带滑动窗口上下文。
        context: [(原文, 译文), ...] 前几条已完成的对照，供模型参考。
        返回与 texts 等长的译文列表。
        """
        # 构建上下文参考段
        ctx_block = ""
        if context:
            ctx_lines = "\n".join(
                f"  [{i+1}] {src} → {tgt}"
                for i, (src, tgt) in enumerate(context)
            )
            ctx_block = (
                f"【已翻译上文（仅供参考语境，禁止重复输出）】\n{ctx_lines}\n\n"
            )

        # 构建待翻译块，带编号方便解析
        batch_text = "\n".join(
            f"[{i+1}] {t}" for i, t in enumerate(texts)
        )

        user_msg = (
            f"{ctx_block}"
            f"【请将以下 {len(texts)} 条日文字幕逐条翻译为简体中文】\n"
            f"严格按照 [编号] 译文 格式输出，每条占一行，不要合并或省略任何条目。\n\n"
            f"{batch_text}"
        )

        payload = {
            "model":   self.model,
            "stream":  False,
            "options": self.GPU_OPTIONS,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req  = urllib.request.Request(self.url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        raw = result["message"]["content"].strip()
        return self._parse_batch(raw, texts)

    def _parse_batch(self, raw: str, originals: List[str]) -> List[str]:
        """
        解析批量翻译结果。
        期望格式：[1] 译文\n[2] 译文\n...
        容错：数量不对时降级为逐条翻译。
        """
        lines = raw.splitlines()
        parsed = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 匹配 [N] 或 N. 或 N、开头
            m = re.match(r'^\[(\d+)\]\s*(.+)$', line)
            if not m:
                m = re.match(r'^(\d+)[\.、．]\s*(.+)$', line)
            if m:
                idx = int(m.group(1))
                parsed[idx] = m.group(2).strip()

        # 按编号还原，缺失的条目降级单条翻译
        results = []
        for i, original in enumerate(originals, start=1):
            if i in parsed:
                results.append(parsed[i])
            else:
                # 单条降级
                try:
                    results.append(self._translate_one(original))
                except Exception:
                    results.append(original)

        return results

    def translate_blocks(
        self,
        texts: List[str],
        progress_callback=None,
        stop_event=None,
    ) -> List[str]:
        """
        批量翻译 + 滑动上下文窗口。
        每批 BATCH_SIZE 条打包为一个请求，
        同时携带前 CONTEXT_SIZE 条已译结果供模型参考。
        """
        results  = []
        total    = len(texts)
        context  = []   # [(原文, 译文), ...]，滑动窗口

        for i in range(0, total, self.BATCH_SIZE):
            if stop_event and stop_event.is_set():
                results.extend(texts[i:])
                break

            batch = texts[i: i + self.BATCH_SIZE]

            retries = 0
            while True:
                try:
                    translated_batch = self._translate_batch(batch, context)
                    break
                except Exception:
                    retries += 1
                    if retries >= 3:
                        translated_batch = batch   # 降级：保留原文
                        break
                    time.sleep(2 ** retries)

            results.extend(translated_batch)

            # 更新滑动上下文窗口
            for src, tgt in zip(batch, translated_batch):
                context.append((src, tgt))
            context = context[-self.CONTEXT_SIZE:]   # 只保留最近 N 条

            if progress_callback:
                progress_callback(min(i + self.BATCH_SIZE, total), total)

        return results

    def check_connection(self) -> dict:
        """检查 Ollama 服务是否在线，并返回已安装模型列表"""
        url = "http://localhost:11434/api/tags"
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode('utf-8'))
