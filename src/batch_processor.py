"""
批量处理模块：协调 SRT 解析、翻译、写回和保存
"""
import inspect
from pathlib import Path
from typing import List, Tuple, Callable, Optional

from srt_parser import load_srt_file, save_srt_string, SRTBlock


def process_files(
    files: List[Tuple[str, bytes]],
    translator,
    progress_callback: Callable = None,  # (filename, done, total)
    stop_event=None,                     # threading.Event，用于中断
    output_dir: Optional[Path] = None,   # 每完成一个文件立即写入此目录
    log_callback=None,                   # (raw: str) 每批原始输出回调
) -> List[Tuple[str, bytes]]:
    """
    批量翻译所有 SRT 文件。
    - 每完成一个文件立即写入 output_dir（如果提供）
    - 返回 [(输出文件名, 字节内容), ...] 供调用方使用
    - stop_event 被设置时停止，已完成的文件仍正常返回
    """
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for filename, file_bytes in files:
        if stop_event and stop_event.is_set():
            break

        blocks: List[SRTBlock] = load_srt_file(file_bytes)
        original_texts = ['\n'.join(b.lines) for b in blocks]

        def _cb(done, total):
            if progress_callback:
                progress_callback(filename, done, total)

        sig    = inspect.signature(translator.translate_blocks)
        kwargs = {"progress_callback": _cb}
        if "stop_event" in sig.parameters:
            kwargs["stop_event"] = stop_event
        if "log_callback" in sig.parameters:
            kwargs["log_callback"] = log_callback

        translated_texts = translator.translate_blocks(original_texts, **kwargs)

        for block, translated in zip(blocks, translated_texts):
            block.lines = translated.splitlines() or ['']

        out_bytes = save_srt_string(blocks)
        stem      = filename.rsplit('.', 1)[0]
        out_name  = f"{stem}_zh.srt"

        # 立即写入本地磁盘
        if output_dir:
            (output_dir / out_name).write_bytes(out_bytes)

        results.append((out_name, out_bytes))

    return results
