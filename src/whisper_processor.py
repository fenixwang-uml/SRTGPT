"""
Whisper 转写模块
使用 faster-whisper（比原版快 4-8 倍，内存占用更低）
"""
import os
from pathlib import Path
from typing import List, Tuple, Callable


def find_mp4_files(folder_path: str) -> List[Path]:
    """递归查找目录下所有 mp4 文件"""
    root = Path(folder_path)
    if not root.exists():
        raise FileNotFoundError(f"路径不存在：{folder_path}")
    return sorted(root.rglob("*.mp4"))


def format_timestamp(seconds: float) -> str:
    """将秒数转换为 SRT 时间戳格式 HH:MM:SS,mmm"""
    ms = int(round(seconds * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1_000
    ms %= 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def transcribe_to_srt(
    mp4_path: Path,
    model,                          # faster_whisper.WhisperModel 实例
    language: str = "ja",
) -> str:
    """
    转写单个 mp4 文件，返回 SRT 字符串。
    model 在外部初始化并复用，避免重复加载。
    """
    segments, _ = model.transcribe(
        str(mp4_path),
        language=language,
        beam_size=5,
        vad_filter=True,            # 自动过滤静音段
        vad_parameters={"min_silence_duration_ms": 500},
    )

    srt_blocks = []
    for i, seg in enumerate(segments, start=1):
        start = format_timestamp(seg.start)
        end = format_timestamp(seg.end)
        text = seg.text.strip()
        if text:
            srt_blocks.append(f"{i}\n{start} --> {end}\n{text}")

    return "\n\n".join(srt_blocks) + "\n"


def batch_transcribe(
    mp4_files: List[Path],
    model_size: str = "medium",
    device: str = "cpu",
    compute_type: str = "int8",
    progress_callback: Callable = None,   # (filename, done, total)
) -> List[Tuple[str, bytes]]:
    """
    批量转写 mp4 文件列表，返回 [(srt文件名, srt字节内容), ...]
    model_size: tiny / base / small / medium / large-v3
    device: cpu / cuda
    compute_type: int8（省内存）/ float16（需要 GPU）
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "请先安装 faster-whisper：\n"
            "pip install faster-whisper"
        )

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    total = len(mp4_files)
    results = []

    for i, mp4_path in enumerate(mp4_files, start=1):
        if progress_callback:
            progress_callback(mp4_path.name, i, total)

        srt_str = transcribe_to_srt(mp4_path, model, language="ja")
        srt_name = mp4_path.stem + ".srt"
        results.append((srt_name, srt_str.encode("utf-8")))

    return results
