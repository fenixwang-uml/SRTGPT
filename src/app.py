"""
SRTGPT — 字幕翻译工具
支持多语言 SRT 字幕翻译（DeepL / Ollama）+ 黑名单批处理
"""
import io
import time
import zipfile
import threading
from pathlib import Path

import streamlit as st

from batch_processor import process_files
from translator import DeepLTranslator, OllamaTranslator
from srt_parser import load_srt_file, save_srt_string
import config as cfg_store

_cfg = cfg_store.load()

st.set_page_config(page_title="SRTGPT", page_icon="🌐", layout="centered")

# beforeunload 警告
if "translating" not in st.session_state:
    st.session_state.translating = False
_warn_js   = "window.__w=function(e){e.preventDefault();e.returnValue='';};window.addEventListener('beforeunload',window.__w);"
_remove_js = "window.removeEventListener('beforeunload',window.__w);"
st.markdown(
    f'<img src="x" onerror="{_warn_js if st.session_state.translating else _remove_js}" style="display:none">',
    unsafe_allow_html=True,
)

st.title("🌐 字幕翻译工具 SRTGPT")

# ════════════════════════════════════════════════════════
# 侧边栏
# ════════════════════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ 翻译引擎")
    engine = st.radio("选择翻译后端", ["DeepL API", "本地 Ollama"], horizontal=True)

    st.divider()
    from languages import (
        DEEPL_SOURCE_LANGUAGES, DEEPL_TARGET_LANGUAGES,
        OLLAMA_LANGUAGES, QUALITY_TIERS, stars,
    )

    src_opts = list(DEEPL_SOURCE_LANGUAGES.keys()) if engine == "DeepL API" else list(OLLAMA_LANGUAGES.keys())
    tgt_opts = list(DEEPL_TARGET_LANGUAGES.keys()) if engine == "DeepL API" else list(OLLAMA_LANGUAGES.keys())
    def_src  = _cfg.get("source_lang", "日语")
    def_tgt  = _cfg.get("target_lang", "中文（简体）")

    col_s, col_t = st.columns(2)
    with col_s:
        source_lang_name = st.selectbox("源语言", src_opts,
                                        index=src_opts.index(def_src) if def_src in src_opts else 0)
    with col_t:
        target_lang_name = st.selectbox("目标语言", tgt_opts,
                                        index=tgt_opts.index(def_tgt) if def_tgt in tgt_opts else 0)

    if source_lang_name != _cfg.get("source_lang") or target_lang_name != _cfg.get("target_lang"):
        _cfg["source_lang"] = source_lang_name
        _cfg["target_lang"] = target_lang_name
        cfg_store.save(_cfg)

    tier = QUALITY_TIERS.get(source_lang_name)
    if tier:
        score = tier.get("deepl" if engine == "DeepL API" else "ollama")
        if score is not None and score <= 3:
            st.warning(f"⚠️ {source_lang_name} 在当前引擎下翻译质量一般（{stars(score)}）")
        elif score is None:
            st.error(f"❌ 当前引擎不支持 {source_lang_name}")

    st.divider()

    api_key        = None
    ollama_model   = None
    ollama_preset  = "balanced"
    custom_options = {}
    custom_batch   = 8

    if engine == "DeepL API":
        api_key = st.text_input(
            "DeepL API Key", value=_cfg.get("deepl_api_key", ""),
            type="password", placeholder="xxxx:fx",
            help="Free 版 Key 末尾为 :fx",
        )
        if api_key and api_key != _cfg.get("deepl_api_key", ""):
            _cfg["deepl_api_key"] = api_key
            cfg_store.save(_cfg)
        if api_key and st.button("查询本月用量"):
            try:
                src_code = DEEPL_SOURCE_LANGUAGES.get(source_lang_name, "JA")
                tgt_code = DEEPL_TARGET_LANGUAGES.get(target_lang_name, "ZH")
                usage = DeepLTranslator(api_key, source_lang=src_code, target_lang=tgt_code).check_usage()
                used  = usage.get("character_count", 0)
                limit = usage.get("character_limit", 0)
                pct   = used / limit * 100 if limit else 0
                st.metric("已使用字符数", f"{used:,}")
                st.progress(pct / 100, text=f"{pct:.1f}% / {limit:,}")
            except Exception as e:
                st.error(f"查询失败：{e}")
    else:
        st.caption("Ollama 运行在本机，无需 API Key")
        try:
            info      = OllamaTranslator().check_connection()
            available = [m["name"] for m in info.get("models", [])]
        except Exception:
            available = []

        if available:
            ollama_model = st.selectbox(
                "选择模型", available,
                index=next((i for i, m in enumerate(available) if "qwen" in m.lower()), 0),
            )
            st.success(f"✅ Ollama 在线，{len(available)} 个模型可用")
        else:
            st.error("❌ 无法连接 Ollama，请确认服务已启动")
            ollama_model = st.text_input("手动输入模型名", value="qwen2.5:14b")

        ollama_preset = st.radio(
            "推理模式",
            ["balanced", "throughput", "custom"],
            format_func=lambda x: {
                "balanced":   "⚖️ 均衡（ctx 512，批次 8）",
                "throughput": "🚀 高吞吐（ctx 2048，批次 20）",
                "custom":     "🔧 自定义",
            }[x],
        )

        if ollama_preset == "custom":
            st.warning("⚠️ 自定义模式仅供高级用户，参数设置不当可能导致崩溃。", icon="⚠️")
            with st.expander("展开参数设置", expanded=True):
                b = OllamaTranslator.PRESET_BALANCED
                c1, c2 = st.columns(2)
                with c1:
                    custom_options["num_ctx"]    = st.number_input("num_ctx",    128, 8192, b["num_ctx"],    128)
                    custom_options["num_batch"]  = st.number_input("num_batch",  64,  2048, b["num_batch"],  64)
                    custom_options["num_gpu"]    = st.number_input("num_gpu",    0,   99,   b["num_gpu"],    1)
                    custom_options["num_thread"] = st.number_input("num_thread", 1,   32,   b["num_thread"], 1)
                with c2:
                    custom_options["temperature"]    = st.slider("temperature",    0.0, 1.0, float(b["temperature"]),    0.05)
                    custom_options["repeat_penalty"] = st.slider("repeat_penalty", 1.0, 2.0, float(b["repeat_penalty"]), 0.05)
                    custom_options["top_k"]          = st.number_input("top_k", 1, 100, b["top_k"], 1)
                    custom_options["top_p"]          = st.slider("top_p", 0.1, 1.0, float(b["top_p"]), 0.05)
                custom_batch = st.number_input("翻译批次大小（条/请求）", 1, 50, 8, 1)

    st.divider()
    st.subheader("🚫 字幕黑名单")
    blacklist = _cfg.get("blacklist", [])
    bl_text = st.text_area(
        "通配符规则（每行一条）",
        value="\n".join(blacklist), height=120,
        help="翻译完成后自动过滤匹配条目并重排序号",
    )
    new_bl = [line.strip() for line in bl_text.splitlines() if line.strip()]
    if new_bl != blacklist:
        _cfg["blacklist"] = new_bl
        cfg_store.save(_cfg)
        blacklist = new_bl
    st.caption("* 匹配任意内容，? 匹配单个字符，不区分大小写")
    st.caption("示例：*广告* | 请订阅* | 翻译：??字幕组")
    if blacklist:
        st.caption(f"当前 {len(blacklist)} 条规则")


# ════════════════════════════════════════════════════════
# 主界面 Tabs
# ════════════════════════════════════════════════════════
_tab1, _tab3 = st.tabs(["🌐 翻译", "🚫 黑名单批处理"])


# ════════════════════════════════════════════════════════
# Tab 1 — 翻译
# ════════════════════════════════════════════════════════
with _tab1:

    uploaded  = st.file_uploader("上传 SRT 文件（可多选）", type=["srt"], accept_multiple_files=True)
    all_files = [(f.name, f.read()) for f in uploaded] if uploaded else []

    if all_files:
        out_dir_check = _cfg.get("translate_output_dir", "").strip()
        if out_dir_check:
            out_dir_path = Path(out_dir_check)
            skipped, kept = [], []
            for fname, fbytes in all_files:
                stem = fname.rsplit(".", 1)[0]
                if (out_dir_path / f"{stem}_zh.srt").exists():
                    skipped.append(fname)
                else:
                    kept.append((fname, fbytes))
            if skipped:
                st.warning(f"以下 {len(skipped)} 个文件已存在译文，已跳过：" + "、".join(skipped))
            all_files = kept

    if not all_files and uploaded:
        st.info("所有上传文件均已翻译，无需重复处理。")

    if all_files:
        st.caption(f"已上传 **{len(all_files)}** 个文件：" + "、".join(n for n, _ in all_files))

        from dedup import deduplicate
        enable_dedup = st.toggle("🔧 合并重复字幕（去重）", value=True)
        if enable_dedup:
            default_gap_s = _cfg.get("dedup_max_gap_s", 300)
            max_gap_s = st.slider("最大合并间隔（秒）", 0, 600, default_gap_s, 10)
            if max_gap_s != default_gap_s:
                _cfg["dedup_max_gap_s"] = max_gap_s
                cfg_store.save(_cfg)

            deduped, dedup_rows, total_removed = [], [], 0
            for fname, fbytes in all_files:
                blocks = load_srt_file(fbytes)
                merged, removed = deduplicate(blocks, max_gap_ms=max_gap_s * 1000)
                total_removed += removed
                deduped.append((fname, save_srt_string(merged)))
                dedup_rows.append({"文件名": fname, "原始": len(blocks), "优化后": len(merged), "合并": removed})

            if total_removed > 0:
                with st.expander(f"📋 去重：共合并 {total_removed} 条", expanded=True):
                    st.dataframe(dedup_rows, column_config={
                        "文件名": st.column_config.TextColumn(),
                        "原始":   st.column_config.NumberColumn(format="%d 条"),
                        "优化后": st.column_config.NumberColumn(format="%d 条"),
                        "合并":   st.column_config.NumberColumn(format="%d 条"),
                    }, hide_index=True, width="stretch")
            else:
                st.success("✅ 未发现重复字幕")
            all_files = deduped

        file_rows, total_chars, total_blocks_all, sample_texts = [], 0, 0, []
        for fname, fbytes in all_files:
            blocks = load_srt_file(fbytes)
            chars  = sum(len("\n".join(b.lines)) for b in blocks)
            total_chars += chars
            total_blocks_all += len(blocks)
            file_rows.append({"文件名": fname, "字幕条数": len(blocks), "字符数": chars})
            sample_texts += ["\n".join(b.lines) for b in blocks]

        panel_title = "📊 预计 DeepL 用量" if engine == "DeepL API" else "📊 预计翻译用时"
        with st.expander(panel_title, expanded=True):
            st.dataframe(file_rows, column_config={
                "文件名":   st.column_config.TextColumn(),
                "字幕条数": st.column_config.NumberColumn(format="%d 条"),
                "字符数":   st.column_config.NumberColumn(format="%d 字符"),
            }, hide_index=True, width="stretch")
            st.divider()
            col_a, col_b = st.columns(2)
            col_a.metric("总字幕条数", f"{total_blocks_all:,} 条")

            if engine == "DeepL API":
                col_a.metric("预计消耗字符", f"{total_chars:,}")
                if api_key:
                    try:
                        src_code  = DEEPL_SOURCE_LANGUAGES.get(source_lang_name, "JA")
                        tgt_code  = DEEPL_TARGET_LANGUAGES.get(target_lang_name, "ZH")
                        usage     = DeepLTranslator(api_key, source_lang=src_code, target_lang=tgt_code).check_usage()
                        used      = usage.get("character_count", 0)
                        limit     = usage.get("character_limit", 0)
                        remaining = limit - used
                        enough    = total_chars <= remaining
                        after_pct = (used + total_chars) / limit if limit else 1
                        col_b.metric("账户剩余配额", f"{remaining:,} 字符",
                                     delta="充足 ✅" if enough else "不足 ⚠️",
                                     delta_color="normal" if enough else "inverse")
                        st.progress(min(after_pct, 1.0),
                                    text=f"翻译后已用：{used+total_chars:,} / {limit:,}（{min(after_pct*100,100):.1f}%）")
                        if not enough:
                            st.warning(f"剩余配额（{remaining:,}）少于本次消耗（{total_chars:,}），建议分批处理。")
                    except Exception:
                        col_b.metric("账户剩余配额", "查询失败")
                else:
                    col_b.metric("账户剩余配额", "请先填入 API Key")
            else:
                col_b.metric("费用", "免费 ✅")
                bench_n = st.select_slider("测速采样条数", options=[3, 5, 10, 20, 50], value=10)
                if st.button("⏱️ 测速并预估用时", type="secondary"):
                    bench_status = st.empty()
                    bench_bar    = st.progress(0)
                    bench_status.info(f"正在用 {bench_n} 条字幕模拟翻译流程…")

                    def on_bench_progress(done, total, phase):
                        bench_bar.progress(done / total, text=f"{phase}：{done}/{total} 条")

                    try:
                        tr_bench = OllamaTranslator(
                            model=ollama_model, preset=ollama_preset,
                            custom_options=custom_options, custom_batch=custom_batch,
                            source_lang=source_lang_name, target_lang=target_lang_name,
                        )
                        secs_per_item, factor = tr_bench.benchmark(
                            sample_texts, n=bench_n, progress_callback=on_bench_progress,
                        )
                        bench_bar.empty()
                        bench_status.empty()
                        total_secs = secs_per_item * total_blocks_all * factor
                        h = int(total_secs // 3600)
                        m = int((total_secs % 3600) // 60)
                        s = int(total_secs % 60)
                        time_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s" if m else f"{s}s"
                        c1, c2 = st.columns(2)
                        c1.metric("单条平均耗时", f"{secs_per_item:.1f} 秒")
                        c2.metric("预计总用时", f"≈ {time_str}", help="基于真实翻译流程实测")
                    except Exception as e:
                        bench_bar.empty()
                        bench_status.error(f"测速失败：{e}")

    output_dir = st.text_input(
        "翻译结果保存路径（可选）",
        value=_cfg.get("translate_output_dir", ""),
        placeholder=r"例如 D:\Subtitles\translated",
        help="填写后每完成一个文件立即保存，留空则仅提供下载",
    )
    if output_dir and output_dir != _cfg.get("translate_output_dir", ""):
        _cfg["translate_output_dir"] = output_dir
        cfg_store.save(_cfg)

    ready = (engine == "本地 Ollama" and ollama_model) or (engine == "DeepL API" and api_key)
    if st.button("🚀 开始翻译", disabled=not (ready and all_files), type="primary"):

        if engine == "DeepL API":
            src_code   = DEEPL_SOURCE_LANGUAGES.get(source_lang_name, "JA")
            tgt_code   = DEEPL_TARGET_LANGUAGES.get(target_lang_name, "ZH")
            translator = DeepLTranslator(api_key, source_lang=src_code, target_lang=tgt_code)
        else:
            translator = OllamaTranslator(
                model=ollama_model, preset=ollama_preset,
                custom_options=custom_options, custom_batch=custom_batch,
                source_lang=source_lang_name, target_lang=target_lang_name,
            )

        status     = st.empty()
        bar_blocks = st.progress(0)
        bar_files  = st.progress(0)
        stop_btn   = st.empty()
        result_box = st.empty()

        if engine == "本地 Ollama":
            log_expander  = st.expander("🔍 模型原始输出（按批）", expanded=False)
            log_container = log_expander.empty()
            log_entries, log_queue, log_counter = [], [], [0]
            def on_log(raw):
                log_counter[0] += 1
                log_queue.append((log_counter[0], raw))
            log_cb = on_log
        else:
            log_cb, log_queue, log_entries, log_container = None, [], [], None

        total_files      = len(all_files)
        total_blocks_cnt = sum(len(load_srt_file(fb)) for _, fb in all_files)
        stop_event       = threading.Event()
        zip_result       = [None]
        error_box        = [None]
        progress_state   = {"filename": "", "blocks_done": 0, "blocks_total": 1,
                            "files_done": 0, "global_done": 0}

        def on_progress(filename, done, total):
            progress_state.update({"filename": filename, "blocks_done": done, "blocks_total": total})
            if done == total:
                progress_state["files_done"]  += 1
                progress_state["global_done"] += total

        def run_translation():
            try:
                zip_result[0] = process_files(
                    all_files, translator,
                    progress_callback=on_progress,
                    stop_event=stop_event,
                    output_dir=Path(output_dir.strip()) if output_dir.strip() else None,
                    log_callback=log_cb,
                    blacklist=blacklist if blacklist else None,
                )
            except Exception as e:
                error_box[0] = e

        status.info("翻译进行中，请稍候…")
        thread = threading.Thread(target=run_translation, daemon=True)
        thread.start()
        st.session_state.translating = True

        btn_counter = [0]
        while thread.is_alive():
            s           = progress_state
            global_done = s["global_done"] + s["blocks_done"]
            bar_blocks.progress(
                min(global_done / total_blocks_cnt, 1.0) if total_blocks_cnt else 0,
                text=f"字幕进度：{global_done:,} / {total_blocks_cnt:,} 条" +
                     (f"（{s['filename']}）" if s["filename"] else ""),
            )
            bar_files.progress(
                min(s["files_done"] / total_files, 1.0) if total_files else 0,
                text=f"文件进度：{s['files_done']} / {total_files} 个文件",
            )
            if engine == "本地 Ollama":
                btn_counter[0] += 1
                if stop_btn.button("⏹️ 中断翻译", key=f"stop_{btn_counter[0]}"):
                    stop_event.set()
                    status.warning("正在中断，等待当前条目完成…")
                if log_queue:
                    log_entries.extend(log_queue)
                    log_queue.clear()
                    n, text = log_entries[-1]
                    log_container.code(f"─── 批次 {n} ───\n{text}", language=None)
            time.sleep(0.5)

        bar_blocks.progress(1.0, text=f"字幕进度：{total_blocks_cnt:,} / {total_blocks_cnt:,} 条")
        bar_files.progress(1.0, text=f"文件进度：{total_files} / {total_files} 个文件")
        stop_btn.empty()
        st.session_state.translating = False

        if error_box[0]:
            status.error(f"❌ 翻译出错：{error_box[0]}")
            st.exception(error_box[0])
        elif stop_event.is_set():
            status.warning(f"⚠️ 已中断，完成 {progress_state['files_done']}/{total_files} 个文件")
        else:
            msg = f"✅ 全部 {total_files} 个文件翻译完成"
            if output_dir.strip():
                msg += f"，已保存至 {output_dir.strip()}"
            status.success(msg)

        if zip_result[0]:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for out_name, out_bytes in zip_result[0]:
                    zf.writestr(out_name, out_bytes)
            zip_buf.seek(0)
            label = "📦 下载已翻译部分" if stop_event.is_set() else "📦 下载 ZIP 压缩包"
            fname = "translated_partial.zip" if stop_event.is_set() else "translated_subtitles.zip"
            result_box.download_button(label=label, data=zip_buf.read(),
                                       file_name=fname, mime="application/zip",
                                       type="secondary" if stop_event.is_set() else "primary")


# ════════════════════════════════════════════════════════
# Tab 3 — 黑名单批处理
# ════════════════════════════════════════════════════════
with _tab3:
    st.subheader("🚫 黑名单批量处理")
    st.caption("上传已翻译的中文 SRT 文件，自动过滤黑名单条目并重排序号")

    if not blacklist:
        st.warning("⚠️ 侧边栏黑名单为空，请先在左侧添加通配符规则再处理。")

    bl3_uploaded = st.file_uploader(
        "上传 _zh.srt 文件（可多选）",
        type=["srt"],
        accept_multiple_files=True,
        key="bl3_uploader",
    )

    bl3_output = st.text_input(
        "处理后保存路径（可选）",
        value=_cfg.get("bl3_output_dir", ""),
        placeholder=r"例如 D:\Subtitles\cleaned",
        help="留空则仅提供下载",
        key="bl3_out",
    )
    if bl3_output and bl3_output != _cfg.get("bl3_output_dir", ""):
        _cfg["bl3_output_dir"] = bl3_output
        cfg_store.save(_cfg)

    if bl3_uploaded and blacklist:
        bl3_files = [(f.name, f.read()) for f in bl3_uploaded]
        st.caption(f"已上传 **{len(bl3_files)}** 个文件，将应用 {len(blacklist)} 条规则")

        if st.button("🚫 开始黑名单处理", type="primary"):
            from blacklist import apply_blacklist

            out_path = Path(bl3_output.strip()) if bl3_output.strip() else None
            if out_path:
                out_path.mkdir(parents=True, exist_ok=True)

            bl3_results, bl3_rows = [], []
            progress = st.progress(0)

            for idx, (fname, fbytes) in enumerate(bl3_files):
                blocks           = load_srt_file(fbytes)
                cleaned, removed = apply_blacklist(blocks, blacklist)
                out_bytes        = save_srt_string(cleaned)
                stem             = fname.rsplit(".", 1)[0]
                out_name         = f"{stem}_clean.srt"

                if out_path:
                    (out_path / out_name).write_bytes(out_bytes)

                bl3_results.append((out_name, out_bytes))
                bl3_rows.append({
                    "文件名":   fname,
                    "原始条数": len(blocks),
                    "处理后":   len(cleaned),
                    "删除条数": removed,
                })
                progress.progress((idx + 1) / len(bl3_files))

            total_deleted = sum(r["删除条数"] for r in bl3_rows)
            st.success(f"✅ 处理完成，共删除 {total_deleted} 条")
            st.dataframe(
                bl3_rows,
                column_config={
                    "文件名":   st.column_config.TextColumn(),
                    "原始条数": st.column_config.NumberColumn(format="%d 条"),
                    "处理后":   st.column_config.NumberColumn(format="%d 条"),
                    "删除条数": st.column_config.NumberColumn(format="%d 条"),
                },
                hide_index=True,
                width="stretch",
            )

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, data in bl3_results:
                    zf.writestr(name, data)
            zip_buf.seek(0)
            st.download_button(
                "📦 下载处理后 ZIP",
                data=zip_buf.read(),
                file_name="blacklist_cleaned.zip",
                mime="application/zip",
            )
