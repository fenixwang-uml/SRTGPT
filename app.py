"""
批量日文字幕翻译工具 — Streamlit 界面
"""
import streamlit as st
import threading
from batch_processor import process_files
from translator import DeepLTranslator

# ── 页面配置 ────────────────────────────────────────────
st.set_page_config(
    page_title="日文字幕翻译工具",
    page_icon="🎌",
    layout="centered",
)

st.title("🎌 日文 SRT 字幕翻译工具")
st.caption("上传 .srt 文件 → DeepL 翻译为中文 → 打包下载")

# ── 侧边栏：API Key 设置 ─────────────────────────────────
with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input(
        "DeepL API Key",
        type="password",
        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx",
        help="Free 版 Key 末尾为 :fx；Pro 版无此后缀"
    )

    # 用量查询
    if api_key and st.button("查询本月用量"):
        try:
            tr = DeepLTranslator(api_key)
            usage = tr.check_usage()
            used = usage.get('character_count', 0)
            limit = usage.get('character_limit', 0)
            pct = used / limit * 100 if limit else 0
            st.metric("已使用字符数", f"{used:,}")
            st.progress(pct / 100, text=f"{pct:.1f}% / {limit:,}")
        except Exception as e:
            st.error(f"查询失败：{e}")

    st.divider()
    st.markdown("""
**使用说明**
1. 填入 DeepL API Key
2. 上传一个或多个 `.srt` 文件
3. 点击「开始翻译」
4. 下载翻译好的 ZIP 压缩包
""")

# ── 主界面：文件上传 ─────────────────────────────────────
uploaded = st.file_uploader(
    "上传 SRT 文件（可多选）",
    type=["srt"],
    accept_multiple_files=True,
)

if uploaded:
    st.info(f"已选择 **{len(uploaded)}** 个文件：" +
            "、".join(f.name for f in uploaded))

# ── 翻译按钮 ─────────────────────────────────────────────
if st.button("🚀 开始翻译", disabled=not (api_key and uploaded), type="primary"):

    if not api_key:
        st.error("请先在左侧填入 DeepL API Key")
        st.stop()

    translator = DeepLTranslator(api_key)
    files = [(f.name, f.read()) for f in uploaded]

    # 进度区域
    status_text = st.empty()
    progress_bar = st.progress(0)

    # 跟踪所有文件的总字幕条数进度
    total_files = len(files)
    completed_files = [0]  # 用列表包装以支持闭包修改
    lock = threading.Lock()

    def on_progress(filename, done, total):
        with lock:
            # 当一个文件翻译完成时计入
            if done == total:
                completed_files[0] += 1
            pct = (completed_files[0] / total_files)
            progress_bar.progress(
                min(pct, 1.0),
                text=f"正在翻译：{filename}（{done}/{total} 条）"
            )

    status_text.info("翻译进行中，请稍候…")

    try:
        zip_bytes = process_files(files, translator, progress_callback=on_progress)
        progress_bar.progress(1.0, text="翻译完成！")
        status_text.success(f"✅ 全部 {total_files} 个文件翻译完成")

        st.download_button(
            label="📦 下载翻译后的 ZIP 压缩包",
            data=zip_bytes,
            file_name="translated_subtitles.zip",
            mime="application/zip",
            type="primary",
        )

    except Exception as e:
        status_text.error(f"❌ 翻译出错：{e}")
        st.exception(e)
