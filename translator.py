"""
DeepL 翻译模块
使用批量拼接策略：将多条字幕合并为一次请求，减少 API 调用次数
"""
import time
import urllib.request
import urllib.parse
import json
from typing import List

# 批次大小：每次最多合并翻译的字幕条数
BATCH_SIZE = 50
# 条目分隔符（不会出现在日语字幕中）
SEP = "\n⚡\n"


class DeepLTranslator:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        # Free 版和 Pro 版使用不同的域名
        if self.api_key.endswith(':fx'):
            self.base_url = "https://api-free.deepl.com/v2"
        else:
            self.base_url = "https://api.deepl.com/v2"

    def _request(self, texts: List[str]) -> List[str]:
        """向 DeepL API 发送一批翻译请求"""
        url = f"{self.base_url}/translate"
        payload = {
            "auth_key": self.api_key,
            "text": texts,
            "source_lang": "JA",
            "target_lang": "ZH",
        }
        data = urllib.parse.urlencode(payload, doseq=True).encode('utf-8')
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

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
        采用批次合并策略：每批 BATCH_SIZE 条合并为一个字符串发送。
        progress_callback(done, total) 用于更新进度条。
        """
        results = []
        total = len(texts)
        done = 0

        for i in range(0, total, BATCH_SIZE):
            batch = texts[i: i + BATCH_SIZE]

            # 合并为一个字符串，用 SEP 分隔
            merged = SEP.join(batch)

            retries = 0
            while retries < 5:
                try:
                    translated_list = self._request([merged])
                    translated_merged = translated_list[0]
                    break
                except Exception as e:
                    retries += 1
                    wait = 2 ** retries
                    if retries >= 5:
                        # 全部重试失败：保留原文
                        translated_merged = merged
                    else:
                        time.sleep(wait)

            # 按分隔符拆回各条
            parts = translated_merged.split(SEP)

            # 如果分隔符被翻译改动，数量对不上时做降级处理
            if len(parts) != len(batch):
                parts = batch  # 降级：保留原文

            results.extend(parts)
            done += len(batch)

            if progress_callback:
                progress_callback(done, total)

            # 请求间隔，避免触发速率限制
            if i + BATCH_SIZE < total:
                time.sleep(0.3)

        return results

    def check_usage(self):
        """查询当月 API 用量"""
        url = f"{self.base_url}/usage"
        payload = urllib.parse.urlencode({"auth_key": self.api_key}).encode()
        req = urllib.request.Request(url, data=payload, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
