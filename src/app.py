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
            type="password",
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx",
            help="Free 版 Key 末尾为 :fx",
        )
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
        ollama_model = None

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


# ── 文件上传 ─────────────────────────────────────────────
uploaded = st.file_uploader(
    "上传 SRT 文件（可多选）",
    type=["srt"],
    accept_multiple_files=True,
)

all_files = [(f.name, f.read()) for f in uploaded] if uploaded else []

if all_files:
    st.caption(f"共 **{len(all_files)}** 个文件：" +
               "、".join(name for name, _ in all_files))

    # ── 信息面板 ─────────────────────────────────────────
    from srt_parser import load_srt_file

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
            if st.button("⏱️ 测速并预估用时", type="secondary"):
                with st.spinner("正在用 3 条字幕测速，请稍候…"):
                    try:
                        secs_per_item, factor = OllamaTranslator(
                            model=ollama_model
                        ).benchmark(sample_texts, n=3)
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
                                  help=f"上下文开销修正系数：×{factor:.2f}（实测）")
                    except Exception as e:
                        st.error(f"测速失败：{e}")

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
        translator = OllamaTranslator(model=ollama_model)

    import threading
    status       = st.empty()
    progress_bar = st.progress(0)
    stop_btn     = st.empty()
    result_box   = st.empty()

    total_files    = len(all_files)
    stop_event     = threading.Event()
    zip_result     = [None]
    error_box      = [None]
    progress_state = {"filename": "", "done": 0, "total": 1, "files_done": 0}

    def on_translate_progress(filename, done, total):
        progress_state["filename"] = filename
        progress_state["done"]     = done
        progress_state["total"]    = total
        if done == total:
            progress_state["files_done"] += 1

    def run_translation():
        try:
            zip_result[0] = process_files(
                all_files,
                translator,
                progress_callback=on_translate_progress,
                stop_event=stop_event,
            )
        except Exception as e:
            error_box[0] = e

    status.info("翻译进行中，请稍候…")
    thread = threading.Thread(target=run_translation, daemon=True)
    thread.start()

    btn_counter = [0]
    while thread.is_alive():
        s   = progress_state
        pct = s["files_done"] / total_files if total_files else 0
        progress_bar.progress(
            min(pct, 1.0),
            text=f"正在翻译：{s['filename']}（{s['done']}/{s['total']} 条）"
                 if s["filename"] else "准备中…",
        )
        if engine == "本地 Ollama":
            btn_counter[0] += 1
            if stop_btn.button("⏹️ 中断翻译", key=f"stop_btn_{btn_counter[0]}"):
                stop_event.set()
                status.warning("正在中断，等待当前条目完成…")
        time.sleep(0.5)

    stop_btn.empty()

    if error_box[0]:
        status.error(f"❌ 翻译出错：{error_box[0]}")
        st.exception(error_box[0])
    elif stop_event.is_set():
        status.warning(
            f"⚠️ 已中断，完成 {progress_state['files_done']}/{total_files} 个文件，"
            "未翻译条目已保留日文原文。"
        )
        result_box.download_button(
            label="📦 下载已翻译部分",
            data=zip_result[0],
            file_name="translated_partial.zip",
            mime="application/zip",
        )
    else:
        progress_bar.progress(1.0, text="翻译完成！")
        status.success(f"✅ 全部 {total_files} 个文件翻译完成")
        result_box.download_button(
            label="📦 下载翻译后的 ZIP 压缩包",
            data=zip_result[0],
            file_name="translated_subtitles.zip",
            mime="application/zip",
            type="primary",
        )
