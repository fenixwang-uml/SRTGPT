"""
批量处理模块：协调 SRT 解析、翻译、写回和打包
"""
import io
import zipfile
from typing import List, Tuple, Callable

from srt_parser import load_srt_file, save_srt_string, SRTBlock
from translator import DeepLTranslator


def process_files(
    files: List[Tuple[str, bytes]],
    translator,
    progress_callback: Callable = None,
    stop_event=None,                      # threading.Event，用于中断
) -> bytes:
    """
    批量翻译所有 SRT 文件，返回 ZIP 压缩包字节。
    stop_event 被设置时，当前文件翻译到一半会停止，
    已完成的文件仍打入 ZIP。
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, file_bytes in files:
            if stop_event and stop_event.is_set():
                break

            blocks: List[SRTBlock] = load_srt_file(file_bytes)
            original_texts = ['\n'.join(b.lines) for b in blocks]

            def _cb(done, total):
                if progress_callback:
                    progress_callback(filename, done, total)

            # 只有 OllamaTranslator 接受 stop_event 参数
            import inspect
            sig = inspect.signature(translator.translate_blocks)
            kwargs = {"progress_callback": _cb}
            if "stop_event" in sig.parameters:
                kwargs["stop_event"] = stop_event

            translated_texts = translator.translate_blocks(
                original_texts, **kwargs
            )

            for block, translated in zip(blocks, translated_texts):
                block.lines = translated.splitlines() or ['']

            out_bytes = save_srt_string(blocks)
            stem = filename.rsplit('.', 1)[0]
            zf.writestr(f"{stem}_zh.srt", out_bytes)

    zip_buffer.seek(0)
    return zip_buffer.read()
