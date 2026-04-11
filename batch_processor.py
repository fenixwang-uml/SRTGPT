"""
批量处理模块：协调 SRT 解析、翻译、写回和打包
"""
import io
import zipfile
from typing import List, Tuple, Callable

from srt_parser import load_srt_file, save_srt_string, SRTBlock
from translator import DeepLTranslator


def process_files(
    files: List[Tuple[str, bytes]],          # [(文件名, 字节内容), ...]
    translator: DeepLTranslator,
    progress_callback: Callable = None,       # (文件名, 条数done, 条数total)
) -> bytes:
    """
    批量翻译所有 SRT 文件，返回 ZIP 压缩包的字节内容。
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, file_bytes in files:
            blocks: List[SRTBlock] = load_srt_file(file_bytes)

            # 提取所有文本行（每个 block 可能多行，用 \n 拼合后翻译）
            original_texts = ['\n'.join(b.lines) for b in blocks]

            def _cb(done, total):
                if progress_callback:
                    progress_callback(filename, done, total)

            translated_texts = translator.translate_blocks(
                original_texts,
                progress_callback=_cb
            )

            # 回填译文
            for block, translated in zip(blocks, translated_texts):
                block.lines = translated.splitlines() or ['']

            # 序列化并写入 ZIP
            out_bytes = save_srt_string(blocks)
            # 输出文件名：原名加 _zh 后缀
            stem = filename.rsplit('.', 1)[0]
            out_name = f"{stem}_zh.srt"
            zf.writestr(out_name, out_bytes)

    zip_buffer.seek(0)
    return zip_buffer.read()
