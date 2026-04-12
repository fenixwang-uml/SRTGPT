"""
SRTGPT 命令行翻译工具
用法示例：
  python src/translate_cli.py --input D:\srt\ --output D:\translated\
  python src/translate_cli.py --input D:\srt\ --output D:\translated\ --engine deepl
  python src/translate_cli.py --input D:\srt\ --output D:\translated\ --engine ollama --model qwen2.5:14b --benchmark
"""
import argparse
import os
import sys
from pathlib import Path

# 确保 src/ 在 import 路径中
sys.path.insert(0, str(Path(__file__).parent))

import config as cfg_store
from srt_parser import load_srt_file, save_srt_string
from dedup import deduplicate
from translator import DeepLTranslator, OllamaTranslator


# ── 进度显示（不依赖 tqdm，用标准库）────────────────────────
def print_progress(filename: str, done: int, total: int) -> None:
    pct = int(done / total * 40)
    bar = "█" * pct + "░" * (40 - pct)
    print(f"\r  [{bar}] {done}/{total}  {filename}", end="", flush=True)


def print_done() -> None:
    print()


# ── 参数解析 ─────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="SRTGPT — 日文字幕批量翻译工具（命令行版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--input", "-i", required=True,
        help="SRT 文件或包含 SRT 文件的目录"
    )
    parser.add_argument(
        "--output", "-o", required=True,
        help="翻译结果输出目录"
    )
    parser.add_argument(
        "--engine", "-e", default="ollama", choices=["deepl", "ollama"],
        help="翻译引擎（默认：ollama）"
    )
    parser.add_argument(
        "--model", "-m", default="qwen2.5:14b",
        help="Ollama 模型名（默认：qwen2.5:14b）"
    )
    parser.add_argument(
        "--api-key", "-k", default=None,
        help="DeepL API Key（优先级高于 config.json 和环境变量）"
    )
    parser.add_argument(
        "--no-dedup", action="store_true",
        help="禁用去重（默认开启）"
    )
    parser.add_argument(
        "--benchmark", "-b", action="store_true",
        help="Ollama 模式下翻译前先测速并预估总用时"
    )

    return parser.parse_args()


# ── 收集输入文件 ─────────────────────────────────────────────
def collect_srt_files(input_path: str):
    p = Path(input_path)
    if p.is_file() and p.suffix.lower() == ".srt":
        return [p]
    elif p.is_dir():
        files = sorted(p.glob("*.srt"))
        if not files:
            print(f"❌ 目录 {p} 下未找到 SRT 文件")
            sys.exit(1)
        return files
    else:
        print(f"❌ 路径不存在或不是 SRT 文件/目录：{input_path}")
        sys.exit(1)


# ── 获取 DeepL API Key ────────────────────────────────────────
def resolve_api_key(arg_key: str, cfg: dict) -> str:
    if arg_key:
        return arg_key
    if env_key := os.environ.get("DEEPL_API_KEY"):
        return env_key
    if cfg_key := cfg.get("deepl_api_key"):
        return cfg_key
    print("❌ 未找到 DeepL API Key，请通过以下任一方式提供：")
    print("   1. 命令行参数：--api-key <key>")
    print("   2. 环境变量：set DEEPL_API_KEY=<key>")
    print("   3. config.json：{ \"deepl_api_key\": \"<key>\" }")
    sys.exit(1)


# ── 主流程 ───────────────────────────────────────────────────
def main():
    args   = parse_args()
    cfg    = cfg_store.load()
    dedup  = not args.no_dedup

    # 收集文件
    srt_paths = collect_srt_files(args.input)
    print(f"\n📂 找到 {len(srt_paths)} 个 SRT 文件")

    # 读取并去重
    all_files = []
    total_removed = 0
    for p in srt_paths:
        raw = p.read_bytes()
        blocks = load_srt_file(raw)
        if dedup:
            blocks, removed = deduplicate(blocks)
            total_removed += removed
        all_files.append((p.name, save_srt_string(blocks)))

    if dedup and total_removed > 0:
        print(f"🔧 去重完成，共合并 {total_removed} 条重复字幕")
    elif dedup:
        print("✅ 未发现重复字幕")

    # 初始化翻译器
    if args.engine == "deepl":
        api_key    = resolve_api_key(args.api_key, cfg)
        translator = DeepLTranslator(api_key)

        # 费用预估
        try:
            usage     = translator.check_usage()
            used      = usage.get("character_count", 0)
            limit     = usage.get("character_limit", 0)
            remaining = limit - used
            total_chars = sum(
                sum(len(line) for line in load_srt_file(fbytes).lines
                    if hasattr(load_srt_file(fbytes), 'lines'))
                for _, fbytes in all_files
            )
            # 重新算字符数
            total_chars = 0
            for _, fbytes in all_files:
                for b in load_srt_file(fbytes):
                    total_chars += len('\n'.join(b.lines))

            print(f"\n📊 DeepL 用量预估")
            print(f"   本次预计消耗：{total_chars:,} 字符")
            print(f"   账户剩余配额：{remaining:,} 字符", end="")
            if total_chars <= remaining:
                print("  ✅ 配额充足")
            else:
                print("  ⚠️  配额不足，翻译可能中断")
        except Exception as e:
            print(f"⚠️  用量查询失败：{e}")

    else:
        translator = OllamaTranslator(model=args.model)
        print(f"\n🤖 Ollama 模型：{args.model}")

        # 检查连接
        try:
            translator.check_connection()
            print("   ✅ Ollama 服务在线")
        except Exception:
            print("   ❌ 无法连接 Ollama，请确认服务已启动")
            sys.exit(1)

        # 测速预估
        if args.benchmark:
            print("   ⏱️  正在测速（3 条样本）…", end="", flush=True)
            sample_texts = []
            total_blocks = 0
            for _, fbytes in all_files:
                blocks = load_srt_file(fbytes)
                total_blocks += len(blocks)
                sample_texts += ['\n'.join(b.lines) for b in blocks]
            try:
                secs, factor = translator.benchmark(sample_texts, n=3)
                total_secs   = secs * total_blocks * factor
                h = int(total_secs // 3600)
                m = int((total_secs % 3600) // 60)
                s = int(total_secs % 60)
                time_str = (f"{h}h {m}m {s}s" if h else f"{m}m {s}s" if m else f"{s}s")
                print(f"\r   ⏱️  单条均时 {secs:.1f}s，预计总用时 ≈ {time_str}"
                      f"（修正系数 ×{factor:.2f}）")
            except Exception as e:
                print(f"\r   ⚠️  测速失败：{e}")

    # 准备输出目录
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n🚀 开始翻译，输出至：{out_dir}\n")

    # 逐文件翻译
    completed = 0
    for filename, file_bytes in all_files:
        blocks        = load_srt_file(file_bytes)
        original_texts = ['\n'.join(b.lines) for b in blocks]

        print(f"  {filename}")

        def _cb(done, total):
            print_progress(filename, done, total)

        import inspect
        sig    = inspect.signature(translator.translate_blocks)
        kwargs = {"progress_callback": _cb}
        # Ollama 支持 stop_event，CLI 暂不使用，保持接口兼容
        translated_texts = translator.translate_blocks(original_texts, **kwargs)
        print_done()

        for block, translated in zip(blocks, translated_texts):
            block.lines = translated.splitlines() or ['']

        stem     = filename.rsplit('.', 1)[0]
        out_name = f"{stem}_zh.srt"
        (out_dir / out_name).write_bytes(save_srt_string(blocks))
        completed += 1
        print(f"  ✅ 已保存 → {out_name}\n")

    print(f"🎉 完成！共翻译 {completed}/{len(all_files)} 个文件")


if __name__ == "__main__":
    main()
