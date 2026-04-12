"""
字幕去重模块
合并相邻且内容相同的字幕条目（时间间隔在 30 秒以内视为连续）
"""
from typing import List, Tuple
from srt_parser import SRTBlock


# 视为连续的最大时间间隔（毫秒）
MAX_GAP_MS = 300_000


def _timecode_to_ms(timecode: str) -> int:
    """将 HH:MM:SS,mmm 格式转换为毫秒整数"""
    time_part, ms_part = timecode.split(",")
    h, m, s = time_part.split(":")
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms_part)


def _end_ms(block: SRTBlock) -> int:
    """取字幕块结束时间（毫秒）"""
    return _timecode_to_ms(block.timecode.split(" --> ")[1].strip())


def _start_ms(block: SRTBlock) -> int:
    """取字幕块开始时间（毫秒）"""
    return _timecode_to_ms(block.timecode.split(" --> ")[0].strip())


def _end_timecode(block: SRTBlock) -> str:
    """取字幕块结束时间字符串"""
    return block.timecode.split(" --> ")[1].strip()


def _start_timecode(block: SRTBlock) -> str:
    """取字幕块开始时间字符串"""
    return block.timecode.split(" --> ")[0].strip()


def _normalize_text(block: SRTBlock) -> str:
    """宽松匹配：strip 每行后连接比较"""
    return "\n".join(line.strip() for line in block.lines).strip()


def deduplicate(
    blocks: List[SRTBlock],
    max_gap_ms: int = MAX_GAP_MS,
) -> Tuple[List[SRTBlock], int]:
    """
    合并相邻内容相同且时间连续（间隔 ≤ 30s）的字幕块。
    序号从原第一条的 index 开始连续重排。

    返回 (去重后的block列表, 合并掉的条数)
    """
    if not blocks:
        return [], 0

    merged = []
    current = blocks[0]

    for nxt in blocks[1:]:
        gap_ms = _start_ms(nxt) - _end_ms(current)
        same_text = _normalize_text(current) == _normalize_text(nxt)

        if same_text and gap_ms <= max_gap_ms:
            # 合并：保留 current 的开始时间，更新结束时间
            new_timecode = f"{_start_timecode(current)} --> {_end_timecode(nxt)}"
            current = SRTBlock(
                index=current.index,
                timecode=new_timecode,
                lines=current.lines,
            )
        else:
            merged.append(current)
            current = nxt

    merged.append(current)

    # 序号从原起始 index 连续重排
    start_index = blocks[0].index
    for i, block in enumerate(merged):
        block.index = start_index + i

    removed = len(blocks) - len(merged)
    return merged, removed
