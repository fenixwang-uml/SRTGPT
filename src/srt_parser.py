"""
SRT 文件解析与写入模块（基于 pysrt）
"""
import io
from dataclasses import dataclass
from typing import List

import pysrt


@dataclass
class SRTBlock:
    index: int
    timecode: str
    lines: List[str]


def load_srt_file(file_bytes: bytes) -> List[SRTBlock]:
    """从字节内容读取 SRT，自动检测编码"""
    for encoding in ('utf-8-sig', 'utf-8', 'shift-jis', 'latin-1'):
        try:
            text = file_bytes.decode(encoding)
            subs = pysrt.from_string(text)
            blocks = []
            for item in subs:
                start = str(item.start).replace('.', ',')
                end   = str(item.end).replace('.', ',')
                blocks.append(SRTBlock(
                    index=item.index,
                    timecode=f"{start} --> {end}",
                    lines=item.text.splitlines(),
                ))
            return blocks
        except Exception:
            continue
    return []


def save_srt_string(blocks: List[SRTBlock]) -> bytes:
    """将 SRTBlock 列表序列化为 UTF-8 字节"""
    subs = pysrt.SubRipFile()
    for block in blocks:
        item = pysrt.SubRipItem()
        item.index = block.index
        start_str, end_str = block.timecode.split(" --> ")
        item.start = pysrt.SubRipTime.from_string(start_str.strip())
        item.end   = pysrt.SubRipTime.from_string(end_str.strip())
        item.text  = "\n".join(block.lines)
        subs.append(item)
    subs.clean_indexes()
    buf = io.StringIO()
    subs.write_into(buf)
    return buf.getvalue().encode('utf-8')
