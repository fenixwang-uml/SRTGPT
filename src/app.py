"""
SRTGPT — 日文字幕翻译工具
上传 SRT 文件 → DeepL 或本地 Ollama 翻译为中文 → ZIP 下载
"""
import streamlit as st
import time
from pathlib import Path

from batch_processor import process_files
from translator import DeepLTranslator, OllamaTranslator
import config as cfg_store

_cfg = cfg_store.load()

st.set_page_config(
    page_title="SRTGPT",
    page_icon="🎌",
    layout="centered",
)

st.title("🎌 日文字幕翻译工具")

# ── 侧边栏 ───────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 翻译引擎")

    engine = st.radio(
        "选择翻译后端",
        ["DeepL API", "本地 Ollama"],
        horizontal=True,
    )

    if engine == "DeepL API":
        api_key = st.text_input(
            "DeepL API Key",
            value=_cfg.get("deepl_api_key", ""),
            type="password",
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx",
            help="Free 版 Key 末尾为 :fx，保存后 CLI 也可使用",
        )
        if api_key and api_key != _cfg.get("deepl_api_key", ""):
            _cfg["deepl_api_key"] = api_key
            cfg_store.save(_cfg)
        if api_key and st.button("查询本月用量"):
            try:
                usage = DeepLTranslator(api_key).check_usage()
                used  = usage.get("character_count", 0)
                limit = usage.get("character_limit", 0)
                pct   = used / limit * 100 if limit else 0
                st.metric("已使用字符数", f"{used:,}")
                st.progress(pct / 100, text=f"{pct:.1f}%  /  上限 {limit:,}")
            except Exception as e:
                st.error(f"查询失败：{e}")
        ollama_model   = None
        ollama_preset  = "balanced"
        custom_options = {}
        custom_batch   = 8

    else:
        api_key = None
        st.caption("Ollama 运行在本机，无需 API Key")
        try:
            info      = OllamaTranslator().check_connection()
            available = [m["name"] for m in info.get("models", [])]
        except Exception:
            available = []

        if available:
            ollama_model = st.selectbox(
                "选择模型",
                available,
                index=next(
                    (i for i, m in enumerate(available) if "qwen" in m.lower()), 0
                ),
            )
            st.success(f"✅ Ollama 在线，{len(available)} 个模型可用")
        else:
            st.error("❌ 无法连接 Ollama，请确认服务已启动")
            ollama_model = st.text_input("手动输入模型名", value="qwen2.5:14b")

        ollama_preset = st.radio(
            "推理模式",
            ["balanced", "throughput", "custom"],
            format_func=lambda x: {
                "balanced":   "⚖️ 均衡模式（ctx 512，批次 8）",
                "throughput": "🚀 高吞吐模式（ctx 2048，批次 20）",
                "custom":     "🔧 自定义模式",
            }[x],
            help="高吞吐模式适合 GPU 利用率偏低时，batch 更大让 GPU 持续工作",
        )

        # 自定义参数输入
        custom_options = {}
        custom_batch   = 8
        if ollama_preset == "custom":
            st.warning(
                "⚠️ 自定义模式仅供高级用户调试使用。"
                "参数设置不当可能导致翻译质量下降、显存溢出或程序崩溃。"
                "如无把握请使用预设模式。",
                icon="⚠️",
            )
            with st.expander("展开参数设置", expanded=True):
                balanced = OllamaTranslator.PRESET_BALANCED
                c1, c2 = st.columns(2)
                with c1:
                    custom_options["num_ctx"] = st.number_input(
                        "num_ctx（上下文长度）",
                        min_value=128, max_value=8192,
                        value=balanced["num_ctx"], step=128,
                        help="模型单次能处理的最大 token 数。过小会截断字幕，过大占用更多显存。",
                    )
                    custom_options["num_batch"] = st.number_input(
                        "num_batch（prompt 批处理大小）",
                        min_value=64, max_value=2048,
                        value=balanced["num_batch"], step=64,
                        help="prompt 阶段并行处理的 token 数。越大 GPU 利用率越高，但显存消耗也增加。",
                    )
                    custom_options["num_gpu"] = st.number_input(
                        "num_gpu（GPU 层数）",
                        min_value=0, max_value=99,
                        value=balanced["num_gpu"], step=1,
                        help="加载到 GPU 的模型层数。99 表示全部，设为 0 则完全用 CPU 推理。",
                    )
                    custom_options["num_thread"] = st.number_input(
                        "num_thread（CPU 线程数）",
                        min_value=1, max_value=32,
                        value=balanced["num_thread"], step=1,
                        help="处理非 GPU 部分使用的 CPU 线程数。一般无需调整。",
                    )
                with c2:
                    custom_options["temperature"] = st.slider(
                        "temperature（随机性）",
                        min_value=0.0, max_value=1.0,
                        value=float(balanced["temperature"]), step=0.05,
                        help="越低输出越确定，翻译场景建议保持 0.1 以下。",
                    )
                    custom_options["repeat_penalty"] = st.slider(
                        "repeat_penalty（重复惩罚）",
                        min_value=1.0, max_value=2.0,
                        value=float(balanced["repeat_penalty"]), step=0.05,
                        help="抑制输出中的重复词语。过高可能导致译文不自然。",
                    )
                    custom_options["top_k"] = st.number_input(
                        "top_k（采样范围）",
                        min_value=1, max_value=100,
                        value=balanced["top_k"], step=1,
                        help="采样时考虑的候选词数量。配合低 temperature 使用，一般无需调整。",
                    )
                    custom_options["top_p"] = st.slider(
                        "top_p（核采样概率）",
                        min_value=0.1, max_value=1.0,
                        value=float(balanced["top_p"]), step=0.05,
                        help="累计概率阈值，超过后截断候选词。一般无需调整。",
                    )

                custom_batch = st.number_input(
                    "翻译批次大小（条/请求）",
                    min_value=1, max_value=50,
                    value=8, step=1,
                    help="每次发给 Ollama 的字幕条数。过大可能超出 num_ctx 导致截断。",
                )


# ── 文件上传 ─────────────────────────────────────────────
uploaded = st.file_uploader(
    "上传 SRT 文件（可多选）",
    type=["srt"],
    accept_multiple_files=True,
)

all_files = [(f.name, f.read()) for f in uploaded] if uploaded else []

if all_files:
    st.caption(f"已上传 **{len(all_files)}** 个文件：" +
               "、".join(name for name, _ in all_files))

    # ── 字幕优化 ─────────────────────────────────────────
    from srt_parser import load_srt_file, save_srt_string
    from dedup import deduplicate

    enable_dedup = st.toggle("🔧 合并重复字幕（去重）", value=True)

    if enable_dedup:
        # 最大间隔滑块，单位秒，读取上次保存的值
        default_gap_s = _cfg.get("dedup_max_gap_s", 300)
        max_gap_s = st.slider(
            "最大合并间隔（秒）",
            min_value=0,
            max_value=600,
            value=default_gap_s,
            step=10,
            help="相邻两条相同字幕之间的时间差在此范围内则合并",
        )
        if max_gap_s != default_gap_s:
            _cfg["dedup_max_gap_s"] = max_gap_s
            cfg_store.save(_cfg)

        max_gap_ms = max_gap_s * 1000

        deduped_files  = []
        dedup_rows     = []
        total_removed  = 0

        for fname, fbytes in all_files:
            blocks          = load_srt_file(fbytes)
            merged, removed = deduplicate(blocks, max_gap_ms=max_gap_ms)
            total_removed  += removed
            deduped_files.append((fname, save_srt_string(merged)))
            dedup_rows.append({
                "文件名":   fname,
                "原始条数": len(blocks),
                "优化后":   len(merged),
                "合并条数": removed,
            })

        if total_removed > 0:
            with st.expander(
                f"📋 去重结果：共合并 {total_removed} 条重复字幕", expanded=True
            ):
                st.dataframe(
                    dedup_rows,
                    column_config={
                        "文件名":   st.column_config.TextColumn(),
                        "原始条数": st.column_config.NumberColumn(format="%d 条"),
                        "优化后":   st.column_config.NumberColumn(format="%d 条"),
                        "合并条数": st.column_config.NumberColumn(format="%d 条"),
                    },
                    hide_index=True,
                    width='stretch',
                )
        else:
            st.success("✅ 未发现重复字幕，无需合并")

        all_files = deduped_files

    # ── 信息面板 ─────────────────────────────────────────

    file_rows    = []
    total_chars  = 0
    total_blocks = 0
    sample_texts = []

    for fname, fbytes in all_files:
        blocks = load_srt_file(fbytes)
        chars  = sum(len('\n'.join(b.lines)) for b in blocks)
        total_chars  += chars
        total_blocks += len(blocks)
        file_rows.append({"文件名": fname, "字幕条数": len(blocks), "字符数": chars})
        sample_texts += ['\n'.join(b.lines) for b in blocks]

    panel_title = "📊 预计 DeepL 用量" if engine == "DeepL API" else "📊 预计翻译用时"

    with st.expander(panel_title, expanded=True):
        st.dataframe(
            file_rows,
            column_config={
                "文件名":   st.column_config.TextColumn(),
                "字幕条数": st.column_config.NumberColumn(format="%d 条"),
                "字符数":   st.column_config.NumberColumn(format="%d 字符"),
            },
            hide_index=True,
            width='stretch',
        )

        st.divider()
        col_a, col_b = st.columns(2)
        col_a.metric("总字幕条数", f"{total_blocks:,} 条")

        if engine == "DeepL API":
            col_a.metric("预计消耗字符", f"{total_chars:,}")
            if api_key:
                try:
                    usage     = DeepLTranslator(api_key).check_usage()
                    used      = usage.get("character_count", 0)
                    limit     = usage.get("character_limit", 0)
                    remaining = limit - used
                    enough    = total_chars <= remaining
                    after_pct = (used + total_chars) / limit if limit else 1
                    col_b.metric(
                        "账户剩余配额",
                        f"{remaining:,} 字符",
                        delta="充足 ✅" if enough else "不足 ⚠️",
                        delta_color="normal" if enough else "inverse",
                    )
                    st.progress(
                        min(after_pct, 1.0),
                        text=(
                            f"翻译后已用：{used + total_chars:,} / {limit:,} 字符"
                            f"（{min(after_pct * 100, 100):.1f}%）"
                        ),
                    )
                    if not enough:
                        st.warning(
                            f"剩余配额（{remaining:,}）少于本次消耗（{total_chars:,}），"
                            "建议分批处理。"
                        )
                except Exception:
                    col_b.metric("账户剩余配额", "查询失败")
            else:
                col_b.metric("账户剩余配额", "请先填入 API Key")

        else:
            col_b.metric("费用", "免费 ✅")

            bench_n = st.select_slider(
                "测速采样条数",
                options=[3, 5, 10, 20, 50],
                value=10,
                help="采样越多结果越准确，但测速本身耗时更长",
            )

            if st.button("⏱️ 测速并预估用时", type="secondary"):
                bench_status = st.empty()
                bench_bar    = st.progress(0)
                bench_status.info(f"正在用 {bench_n} 条字幕模拟真实翻译流程…")

                def on_bench_progress(done, total, phase):
                    bench_bar.progress(
                        done / total,
                        text=f"{phase}：{done}/{total} 条",
                    )

                try:
                    secs_per_item, factor = OllamaTranslator(
                        model=ollama_model, preset=ollama_preset,
                        custom_options=custom_options, custom_batch=custom_batch,
                    ).benchmark(sample_texts, n=bench_n,
                                progress_callback=on_bench_progress)

                    bench_bar.empty()
                    bench_status.empty()

                    total_secs = secs_per_item * total_blocks * factor
                    h = int(total_secs // 3600)
                    m = int((total_secs % 3600) // 60)
                    s = int(total_secs % 60)
                    time_str = (f"{h}h {m}m {s}s" if h
                                else f"{m}m {s}s" if m
                                else f"{s}s")
                    c1, c2 = st.columns(2)
                    c1.metric("单条平均耗时", f"{secs_per_item:.1f} 秒")
                    c2.metric("预计总用时", f"≈ {time_str}",
                              help="基于真实翻译流程实测，与实际用时高度一致")
                except Exception as e:
                    bench_bar.empty()
                    bench_status.error(f"测速失败：{e}")

# ── 翻译输出路径 ─────────────────────────────────────────
output_dir = st.text_input(
    "翻译结果保存路径（可选）",
    value=_cfg.get("translate_output_dir", ""),
    placeholder=r"例如 D:\Subtitles\translated，留空则仅提供下载",
    help="填写后翻译完成的 SRT 文件会同时保存到此目录",
)
if output_dir and output_dir != _cfg.get("translate_output_dir", ""):
    _cfg["translate_output_dir"] = output_dir
    cfg_store.save(_cfg)

# ── 翻译按钮 ─────────────────────────────────────────────
ready = (engine == "本地 Ollama" and ollama_model) or \
        (engine == "DeepL API" and api_key)

if st.button(
    "🚀 开始翻译",
    disabled=not (ready and all_files),
    type="primary",
):
    if engine == "DeepL API":
        translator = DeepLTranslator(api_key)
    else:
        translator = OllamaTranslator(
            model=ollama_model, preset=ollama_preset,
            custom_options=custom_options, custom_batch=custom_batch,
        )

    import threading
    status        = st.empty()
    bar_blocks    = st.progress(0)   # 总字幕条数进度
    bar_files     = st.progress(0)   # 文件数进度
    stop_btn      = st.empty()
    result_box    = st.empty()

    total_files  = len(all_files)
    total_blocks_all = sum(
        len(load_srt_file(fbytes)) for _, fbytes in all_files
    )
    stop_event     = threading.Event()
    zip_result     = [None]
    error_box      = [None]
    progress_state = {
        "filename":     "",
        "blocks_done":  0,   # 当前文件已翻译条数
        "blocks_total": 1,   # 当前文件总条数
        "files_done":   0,
        "global_done":  0,   # 跨所有文件累计已翻译条数
    }

    def on_translate_progress(filename, done, total):
        progress_state["filename"]     = filename
        progress_state["blocks_done"]  = done
        progress_state["blocks_total"] = total
        # 当前文件翻译完才计入全局累计
        if done == total:
            progress_state["files_done"]  += 1
            progress_state["global_done"] += total

    def run_translation():
        try:
            zip_result[0] = process_files(
                all_files,
                translator,
                progress_callback=on_translate_progress,
                stop_event=stop_event,
                output_dir=Path(output_dir.strip()) if output_dir.strip() else None,
            )
        except Exception as e:
            error_box[0] = e

    status.info("翻译进行中，请稍候…")
    thread = threading.Thread(target=run_translation, daemon=True)
    thread.start()

    # 翻译期间注入 beforeunload 警告，防止误关浏览器
    st.markdown("""
        <script>
        window._srtgpt_warn = function(e) {
            e.preventDefault();
            e.returnValue = '翻译正在进行中，确认要离开吗？';
        };
        window.addEventListener('beforeunload', window._srtgpt_warn);
        </script>
    """, unsafe_allow_html=True)

    btn_counter = [0]
    while thread.is_alive():
        s = progress_state

        # 字幕条数进度：已完成文件的条数 + 当前文件已翻译条数
        global_done = s["global_done"] + s["blocks_done"]
        blocks_pct  = global_done / total_blocks_all if total_blocks_all else 0
        bar_blocks.progress(
            min(blocks_pct, 1.0),
            text=f"字幕进度：{global_done:,} / {total_blocks_all:,} 条"
                 + (f"（{s['filename']}）" if s["filename"] else ""),
        )

        # 文件数进度
        files_pct = s["files_done"] / total_files if total_files else 0
        bar_files.progress(
            min(files_pct, 1.0),
            text=f"文件进度：{s['files_done']} / {total_files} 个文件",
        )

        if engine == "本地 Ollama":
            btn_counter[0] += 1
            if stop_btn.button("⏹️ 中断翻译", key=f"stop_btn_{btn_counter[0]}"):
                stop_event.set()
                status.warning("正在中断，等待当前条目完成…")
        time.sleep(0.5)

    # 完成后两条进度条都满
    bar_blocks.progress(1.0, text=f"字幕进度：{total_blocks_all:,} / {total_blocks_all:,} 条")
    bar_files.progress(1.0, text=f"文件进度：{total_files} / {total_files} 个文件")

    stop_btn.empty()

    # 翻译结束，移除关闭警告
    st.markdown("""
        <script>
        window.removeEventListener('beforeunload', window._srtgpt_warn);
        </script>
    """, unsafe_allow_html=True)

    if error_box[0]:
        status.error(f"❌ 翻译出错：{error_box[0]}")
        st.exception(error_box[0])
    elif stop_event.is_set():
        files_done = progress_state["files_done"]
        status.warning(
            f"⚠️ 已中断，完成 {files_done}/{total_files} 个文件，"
            "未翻译条目已保留日文原文。"
        )
    else:
        progress_bar.progress(1.0, text="翻译完成！")
        if output_dir.strip():
            status.success(
                f"✅ 全部 {total_files} 个文件翻译完成，已保存至 {output_dir.strip()}"
            )
        else:
            status.success(f"✅ 全部 {total_files} 个文件翻译完成")

    # 只要有结果就提供下载（含中断情况）
    if zip_result[0]:
        import io, zipfile
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for out_name, out_bytes in zip_result[0]:
                zf.writestr(out_name, out_bytes)
        zip_buffer.seek(0)

        label = "📦 下载已翻译部分" if stop_event.is_set() else "📦 下载 ZIP 压缩包"
        fname = "translated_partial.zip" if stop_event.is_set() else "translated_subtitles.zip"
        result_box.download_button(
            label=label,
            data=zip_buffer.read(),
            file_name=fname,
            mime="application/zip",
            type="primary" if not stop_event.is_set() else "secondary",
        )
