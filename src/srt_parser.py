"""
SRT 文件解析与写入模块
"""
import re
from dataclasses import dataclass
from typing import List


@dataclass
class SRTBlock:
    index: int
    timecode: str
    lines: List[str]  # 可能多行


def detect_encoding(raw: bytes) -> str:
    """简单编码检测：UTF-8-BOM / UTF-8 / Shift-JIS"""
    if raw.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    try:
        raw.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        return 'shift-jis'


def parse_srt(content: str) -> List[SRTBlock]:
    """将 SRT 字符串解析为 SRTBlock 列表"""
    blocks = []
    # 以空行为分隔符切割
    raw_blocks = re.split(r'\n\s*\n', content.strip())

    for raw in raw_blocks:
        lines = raw.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        timecode = lines[1].strip()
        text_lines = lines[2:]
        blocks.append(SRTBlock(index=idx, timecode=timecode, lines=text_lines))

    return blocks


def blocks_to_srt(blocks: List[SRTBlock]) -> str:
    """将 SRTBlock 列表序列化为 SRT 字符串"""
    parts = []
    for b in blocks:
        text = '\n'.join(b.lines)
        parts.append(f"{b.index}\n{b.timecode}\n{text}")
    return '\n\n'.join(parts) + '\n'


def load_srt_file(file_bytes: bytes) -> List[SRTBlock]:
    encoding = detect_encoding(file_bytes)
    content = file_bytes.decode(encoding, errors='replace')
    return parse_srt(content)


def save_srt_string(blocks: List[SRTBlock]) -> bytes:
    """输出 UTF-8（无 BOM）字节，兼容主流播放器"""
    return blocks_to_srt(blocks).encode('utf-8')
