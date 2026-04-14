"""
字幕黑名单模块
使用通配符规则匹配（fnmatch），支持 * 和 ? 占位符
匹配后删除条目并重排序号

通配符示例：
  *广告*       — 包含"广告"的任意内容
  请订阅*      — 以"请订阅"开头
  *字幕组*     — 包含"字幕组"
  翻译：??     — "翻译："后跟任意两个字符
"""
import fnmatch
from typing import List, Tuple
from srt_parser import SRTBlock


def _normalize(text: str) -> str:
    return text.strip()


def apply_blacklist(
    blocks: List[SRTBlock],
    patterns: List[str],
) -> Tuple[List[SRTBlock], int]:
    """
    过滤与通配符规则匹配的字幕条目，并重排序号。
    patterns: 通配符规则列表，如 ["*广告*", "请订阅*"]
    匹配不区分大小写。
    返回 (过滤后的block列表, 删除条数)
    """
    if not patterns:
        return blocks, 0

    active = [p.strip() for p in patterns if p.strip()]
    if not active:
        return blocks, 0

    kept    = []
    removed = 0

    for block in blocks:
        text = _normalize("\n".join(block.lines))
        hit  = any(
            fnmatch.fnmatch(text.lower(), p.lower())
            for p in active
        )
        if hit:
            removed += 1
        else:
            kept.append(block)

    # 重排序号，从原起始序号连续递增
    if kept:
        start = blocks[0].index if blocks else 1
        for i, b in enumerate(kept):
            b.index = start + i

    return kept, removed
