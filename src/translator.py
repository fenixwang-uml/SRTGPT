"""
翻译模块：支持 DeepL API 和本地 Ollama 两种后端
"""
import time
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

    def benchmark(self, samples: List[str], n: int = 3) -> float:
        """用前 n 条真实字幕测速，返回每条平均耗时（秒）"""
        test_texts = [t for t in samples if t.strip()][:n]
        if not test_texts:
            return 3.0

        start = time.time()
        for text in test_texts:
            try:
                self._translate_one(text)
            except Exception:
                pass
        elapsed = time.time() - start
        return elapsed / len(test_texts)

    def translate_blocks(
        self,
        texts: List[str],
        progress_callback=None,
        stop_event=None,        # threading.Event，外部设置后中断翻译
    ) -> List[str]:
        """
        逐条翻译，每条完成后更新进度。
        stop_event 被设置时立即停止，已完成的条目保留译文，
        未完成的条目保留原文。
        """
        results = []
        total = len(texts)

        for i, text in enumerate(texts):
            # 检查中断信号
            if stop_event and stop_event.is_set():
                # 剩余条目填入原文
                results.extend(texts[i:])
                break

            retries = 0
            while True:
                try:
                    translated = self._translate_one(text)
                    break
                except Exception:
                    retries += 1
                    if retries >= 3:
                        translated = text
                        break
                    time.sleep(2 ** retries)

            results.append(translated)

            if progress_callback:
                progress_callback(i + 1, total)

        return results

    def check_connection(self) -> dict:
        """检查 Ollama 服务是否在线，并返回已安装模型列表"""
        url = "http://localhost:11434/api/tags"
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode('utf-8'))
