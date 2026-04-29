"""
翻译模块：支持 DeepL API 和本地 Ollama 两种后端
Ollama 后端通过 prompt_manager 加载外置 system prompt，
支持 standard / pornify 等多种 tone，
使用 <scene> 跨批次上下文替代滑动原文窗口。
"""
import time
import re
import urllib.request
import urllib.parse
import json
from typing import List, Optional, Callable

# 每批最多传给 DeepL 的字幕条数（API 单次请求上限为 50 条）
BATCH_SIZE = 50


class DeepLTranslator:
    def __init__(self, api_key: str, source_lang: str = "JA", target_lang: str = "ZH"):
        self.api_key     = api_key.strip()
        self.source_lang = source_lang
        self.target_lang = target_lang
        if self.api_key.endswith(':fx'):
            self.base_url = "https://api-free.deepl.com/v2"
        else:
            self.base_url = "https://api.deepl.com/v2"

    def _request(self, texts: List[str]) -> List[str]:
        url    = f"{self.base_url}/translate"
        params = [("source_lang", self.source_lang), ("target_lang", self.target_lang)]
        params += [("text", t) for t in texts]
        data   = urllib.parse.urlencode(params).encode('utf-8')
        req    = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        req.add_header('Authorization', f'DeepL-Auth-Key {self.api_key}')
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        return [t['text'] for t in result['translations']]

    def translate_blocks(self, texts: List[str], progress_callback=None, **kwargs) -> List[str]:
        results = []
        total   = len(texts)
        for i in range(0, total, BATCH_SIZE):
            batch   = texts[i: i + BATCH_SIZE]
            retries = 0
            while True:
                try:
                    translated = self._request(batch)
                    if len(translated) != len(batch):
                        translated = batch
                    break
                except Exception:
                    retries += 1
                    if retries >= 5:
                        translated = batch
                        break
                    time.sleep(2 ** retries)
            results.extend(translated)
            if progress_callback:
                progress_callback(len(results), total)
            if i + BATCH_SIZE < total:
                time.sleep(0.3)
        return results

    def check_usage(self):
        url = f"{self.base_url}/usage"
        req = urllib.request.Request(url, method='GET')
        req.add_header('Authorization', f'DeepL-Auth-Key {self.api_key}')
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())


class OllamaTranslator:
    """
    本地 Ollama 翻译后端，针对 4070 Ti (12GB) 优化。
    System prompt 从外置文件加载（prompt_manager），
    跨批次上下文通过 <scene> 标签传递。
    """

    # P0 Fix: num_ctx=512 远小于 prompt 开销（约600 tokens），必然溢出。
    # 重新校准：overhead≈600，tokens_per_line≈90，安全批次=(ctx-600)//90
    # balanced  (2048): safe≈16 → 保守取 10
    # throughput(4096): safe≈39 → 保守取 20
    PRESET_BALANCED = {
        "num_gpu": 99, "num_ctx": 2048, "num_batch": 512,
        "num_thread": 4, "temperature": 0.1, "repeat_penalty": 1.1,
        "top_k": 20, "top_p": 0.9,
    }
    PRESET_THROUGHPUT = {
        "num_gpu": 99, "num_ctx": 4096, "num_batch": 1024,
        "num_thread": 4, "temperature": 0.1, "repeat_penalty": 1.1,
        "top_k": 20, "top_p": 0.9,
    }
    PRESETS = {"balanced": PRESET_BALANCED, "throughput": PRESET_THROUGHPUT}
    BATCH_SIZE_BY_PRESET = {"balanced": 10, "throughput": 20}

    def __init__(
        self,
        model: str = "qwen2.5:14b",
        preset: str = "balanced",
        custom_options: dict = None,
        custom_batch: int = 8,
        source_lang: str = "日语",
        target_lang: str = "简体中文",
        tone: str = "standard",
        custom_prompt_path: Optional[str] = None,
    ):
        self.model               = model
        self.preset              = preset if preset in (*self.PRESETS, "custom") else "balanced"
        self._custom_opts        = custom_options or {}
        self._custom_batch       = custom_batch
        self.source_lang         = source_lang
        self.target_lang         = target_lang
        self.tone                = tone
        self.custom_prompt_path  = custom_prompt_path
        self.url                 = "http://localhost:11434/api/chat"

        # 加载外置 prompt（初始化时完成，避免每批重复 IO）
        from prompt_manager import load_prompt
        self._prompt_set = load_prompt(
            tone=tone,
            source_lang=source_lang,
            target_lang=target_lang,
            custom_path=custom_prompt_path,
        )

    @property
    def GPU_OPTIONS(self):
        if self.preset == "custom":
            return self._custom_opts
        return self.PRESETS[self.preset]

    @property
    def BATCH_SIZE(self):
        if self.preset == "custom":
            return self._custom_batch
        return self.BATCH_SIZE_BY_PRESET[self.preset]

    # ── P1 辅助函数 ──────────────────────────────────────────────────────────

    @staticmethod
    def cap_batch_size(max_batch: int, num_ctx: int) -> int:
        """
        根据 num_ctx 自动上限批次大小，防止上下文溢出。
        参考 WhisperJAV core.py cap_batch_size_for_context()，
        针对我们更轻量的 prompt 格式重新标定参数：
          overhead       = 600  (system prompt + scene + 消息头)
          tokens_per_line = 90  (日语输入≈60 + 中文输出≈30)
        """
        overhead        = 600
        tokens_per_line = 90
        safe = max(3, (num_ctx - overhead) // tokens_per_line)
        capped = min(max_batch, safe)
        if capped < max_batch:
            import warnings
            warnings.warn(
                f"batch_size {max_batch} 超出 num_ctx={num_ctx} 的安全范围，"
                f"已自动缩减为 {capped}。"
            )
        return capped

    @staticmethod
    def compute_num_predict(batch_size: int, num_ctx: int) -> int:
        """
        动态计算 num_predict（Ollama 输出 token 上限），防止模型生成冗长垃圾输出。
        参考 WhisperJAV core.py compute_max_output_tokens()：
          input_per_line  = 60  tokens (日语输入估算)
          output_per_line = 30  tokens (中文译文估算)
          output_tags     = 200 tokens (<summary>/<scene> 标签)
        """
        overhead        = 600
        input_per_line  = 60
        output_per_line = 30
        output_tags     = 200
        available = num_ctx - overhead - (batch_size * input_per_line)
        expected  = (batch_size * output_per_line) + output_tags
        return max(256, min(available, expected))

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def _num_ctx(self) -> int:
        return self.GPU_OPTIONS.get("num_ctx", 2048)

    @property
    def _effective_batch_size(self) -> int:
        return self.cap_batch_size(self.BATCH_SIZE, self._num_ctx)

    @property
    def _runtime_options(self) -> dict:
        """GPU_OPTIONS 加上动态计算的 num_predict"""
        opts = dict(self.GPU_OPTIONS)
        opts["num_predict"] = self.compute_num_predict(
            self._effective_batch_size, self._num_ctx
        )
        return opts

    def _build_user_msg(self, texts: List[str], scene: str) -> str:
        """
        构建用户消息：
        - prompt_header（来自 ### prompt 段）
        - 上一批的 <scene> 摘要（如有）
        - 编号字幕列表
        """
        parts = [self._prompt_set.prompt_header, ""]

        if scene:
            parts += [f"Previous scene context:\n{scene}", ""]

        parts += [
            f"Translate the following {len(texts)} subtitles:",
            "\n".join(f"[{i+1}] {t}" for i, t in enumerate(texts)),
        ]
        return "\n".join(parts)

    def _call_ollama(self, system: str, user: str) -> str:
        """发送请求到 Ollama，返回原始文本输出"""
        payload = {
            "model":   self.model,
            "stream":  False,
            "options": self._runtime_options,   # 含动态 num_predict
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req  = urllib.request.Request(self.url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        # Thinking 模型兼容：Qwen3 等将输出放在 'reasoning' 而非 'content'
        msg = result.get("message", {})
        content = msg.get("content", "").strip()
        if not content:
            content = msg.get("reasoning", "").strip()
        return content

    def _translate_batch(
        self,
        texts: List[str],
        scene: str = "",
        log_callback: Optional[Callable] = None,
    ) -> tuple:
        """
        翻译一批字幕，返回 (译文列表, 新的 scene 字符串)。
        scene 来自上一批的 <scene> 标签，用于跨批次上下文。
        """
        from prompt_manager import extract_tags

        user_msg = self._build_user_msg(texts, scene)
        raw      = self._call_ollama(self._prompt_set.instructions, user_msg)

        if log_callback:
            log_callback(raw)

        tags      = extract_tags(raw)
        new_scene = tags["scene"]
        clean_raw = tags["clean"]

        translated = self._parse_batch(clean_raw, texts)

        # 如果解析结果数量不对，用 retry_instructions 重试一次
        if len(translated) != len(texts):
            retry_user = self._prompt_set.retry_instructions + "\n\n" + user_msg
            raw2       = self._call_ollama(self._prompt_set.instructions, retry_user)
            if log_callback:
                log_callback(f"[RETRY]\n{raw2}")
            tags2      = extract_tags(raw2)
            translated = self._parse_batch(tags2["clean"], texts)
            if tags2["scene"]:
                new_scene = tags2["scene"]

        return translated, new_scene

    def _parse_batch(self, clean_raw: str, originals: List[str]) -> List[str]:
        """
        解析 [N] 格式的批量翻译结果。
        clean_raw 已去掉 <summary>/<scene> 标签。
        """
        parsed = {}
        for line in clean_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^\[(\d+)\]\s*(.+)$', line)
            if not m:
                m = re.match(r'^(\d+)[\.、．]\s*(.+)$', line)
            if m:
                idx = int(m.group(1))
                # 去除行内残留的代码块标记
                text = m.group(2).strip().strip('`').strip()
                parsed[idx] = text

        results = []
        for i, original in enumerate(originals, start=1):
            if i in parsed:
                results.append(parsed[i])
            else:
                # 单条降级：直接翻译
                try:
                    user_one = self._build_user_msg([original], "")
                    raw_one  = self._call_ollama(self._prompt_set.instructions, user_one)
                    from prompt_manager import extract_tags
                    one_parsed = self._parse_batch(extract_tags(raw_one)["clean"], [original])
                    results.append(one_parsed[0] if one_parsed else original)
                except Exception:
                    results.append(original)
        return results

    def _translate_one(self, text: str) -> str:
        """单条翻译（benchmark 用）"""
        user_msg = self._build_user_msg([text], "")
        raw = self._call_ollama(self._prompt_set.instructions, user_msg)
        from prompt_manager import extract_tags
        parsed = self._parse_batch(extract_tags(raw)["clean"], [text])
        return parsed[0] if parsed else text

    def benchmark(self, samples: List[str], n: int = 10, progress_callback=None) -> tuple:
        """用真实翻译流程测速，返回 (单条均时, 修正系数=1.0)"""
        test_texts = [t for t in samples if t.strip()][:n]
        if not test_texts:
            return 3.0, 1.0

        total = len(test_texts)
        done  = [0]

        def _cb(d, t):
            done[0] = d
            if progress_callback:
                progress_callback(d, t, "模拟翻译中")

        start = time.time()
        self.translate_blocks(test_texts, progress_callback=_cb)
        elapsed = time.time() - start

        return elapsed / total, 1.0

    def translate_blocks(
        self,
        texts: List[str],
        progress_callback: Optional[Callable] = None,
        stop_event=None,
        log_callback: Optional[Callable] = None,
        scene_callback: Optional[Callable] = None,  # (scene_text: str) 每批后调用
    ) -> List[str]:
        """
        批量翻译，使用 <scene> 跨批次上下文。
        scene_callback: 每批完成后把最新 scene 文本传给调用方（用于 UI 显示）
        """
        results   = []
        total     = len(texts)
        scene     = ""   # 跨批次场景上下文，由 <scene> 标签积累

        for i in range(0, total, self._effective_batch_size):
            if stop_event and stop_event.is_set():
                results.extend(texts[i:])
                break

            batch   = texts[i: i + self._effective_batch_size]
            retries = 0

            while True:
                try:
                    translated_batch, new_scene = self._translate_batch(
                        batch, scene=scene, log_callback=log_callback
                    )
                    if new_scene:
                        scene = new_scene
                    if scene_callback and scene:
                        scene_callback(scene)
                    break
                except Exception:
                    retries += 1
                    if retries >= 3:
                        translated_batch = batch
                        break
                    time.sleep(2 ** retries)

            results.extend(translated_batch)

            if progress_callback:
                progress_callback(min(i + self._effective_batch_size, total), total)

        return results

    def check_connection(self) -> dict:
        url = "http://localhost:11434/api/tags"
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode('utf-8'))
