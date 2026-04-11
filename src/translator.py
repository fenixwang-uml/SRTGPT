"""
DeepL 翻译模块
使用批量拼接策略：将多条字幕合并为一次请求，减少 API 调用次数
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
