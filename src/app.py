"""
批量日文字幕翻译工具 — Streamlit 界面
Step 1（可选）：内网 MP4 → Whisper 转写 → SRT
Step 2：SRT → DeepL → 中文 SRT → ZIP 下载
"""
import streamlit as st
from pathlib import Path

from batch_processor import process_files
from translator import DeepLTranslator

# ── 页面配置 ────────────────────────────────────────────
st.set_page_config(
    page_title="日文字幕工具",
    page_icon="🎌",
    layout="centered",
)

st.title("🎌 日文字幕处理工具")

# ── 侧边栏：全局设置 ─────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 全局设置")

    api_key = st.text_input(
        "DeepL API Key",
        type="password",
        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx",
        help="Free 版 Key 末尾为 :fx",
    )

    if api_key and st.button("查询本月用量"):
        try:
            tr = DeepLTranslator(api_key)
            usage = tr.check_usage()
            used = usage.get("character_count", 0)
            limit = usage.get("character_limit", 0)
            pct = used / limit * 100 if limit else 0
            st.metric("已使用字符数", f"{used:,}")
            st.progress(pct / 100, text=f"{pct:.1f}%  /  上限 {limit:,}")
        except Exception as e:
            st.error(f"查询失败：{e}")

    st.divider()
    st.markdown("""
**工作流程**
1. **Step 1**（可选）：扫描内网共享文件夹，用 Whisper 将 MP4 转写为 SRT
2. **Step 2**：将 SRT 翻译为中文并打包下载

如果已有 SRT 文件，可直接跳到 Step 2。
""")

# ── Session State 初始化 ─────────────────────────────────
# 用于在 Tab 之间传递 Whisper 生成的 SRT 文件
if "whisper_srts" not in st.session_state:
    st.session_state.whisper_srts = []   # List of (filename, bytes)

# ── 两个 Tab ─────────────────────────────────────────────
tab1, tab2 = st.tabs(["🎬 Step 1：MP4 转写 SRT", "🌐 Step 2：翻译 SRT"])


# ════════════════════════════════════════════════════════
# Tab 1 — Whisper 转写
# ════════════════════════════════════════════════════════
with tab1:
    st.subheader("用 Whisper 从 MP4 生成日文 SRT")

    col1, col2 = st.columns(2)
    with col1:
        model_size = st.selectbox(
            "Whisper 模型",
            ["tiny", "base", "small", "medium", "large-v3"],
            index=3,
            help="模型越大准确率越高，但速度越慢。medium 是日语的推荐选项。",
        )
    with col2:
        device = st.selectbox(
            "运行设备",
            ["cpu", "cuda"],
            index=0,
            help="有 NVIDIA 显卡选 cuda，否则选 cpu",
        )

    network_path = st.text_input(
        "内网共享路径",
        placeholder=r"\\192.168.1.x\共享文件夹\视频",
        help=r"输入已挂载的 UNC 路径，例如 \\192.168.1.10\media\jp_videos",
    )

    # 扫描文件
    mp4_files = []
    if network_path:
        try:
            from whisper_processor import find_mp4_files
            mp4_files = find_mp4_files(network_path)
            if mp4_files:
                st.success(f"找到 **{len(mp4_files)}** 个 MP4 文件：")
                with st.expander("查看文件列表"):
                    for f in mp4_files:
                        st.text(f.name)
            else:
                st.warning("该路径下未找到 MP4 文件")
        except FileNotFoundError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"扫描失败：{e}")

    # 开始转写
    if st.button(
        "🎙️ 开始转写",
        disabled=not mp4_files,
        type="primary",
    ):
        from whisper_processor import batch_transcribe

        compute_type = "float16" if device == "cuda" else "int8"
        status = st.empty()
        progress_bar = st.progress(0)

        def on_whisper_progress(filename, done, total):
            pct = done / total
            progress_bar.progress(pct, text=f"正在转写：{filename}（{done}/{total}）")

        status.info(f"正在加载 Whisper {model_size} 模型，首次运行需下载…")

        try:
            results = batch_transcribe(
                mp4_files,
                model_size=model_size,
                device=device,
                compute_type=compute_type,
                progress_callback=on_whisper_progress,
            )
            st.session_state.whisper_srts = results
            progress_bar.progress(1.0, text="转写完成！")
            status.success(
                f"✅ {len(results)} 个文件转写完成，"
                "已传递到 Step 2，可直接进行翻译。"
            )
        except ImportError as e:
            status.error(str(e))
        except Exception as e:
            status.error(f"转写出错：{e}")
            st.exception(e)


# ════════════════════════════════════════════════════════
# Tab 2 — 翻译
# ════════════════════════════════════════════════════════
with tab2:
    st.subheader("将日文 SRT 翻译为中文")

    # 来源 A：Step 1 传递过来的文件
    whisper_srts = st.session_state.whisper_srts
    if whisper_srts:
        st.info(
            f"已从 Step 1 接收到 **{len(whisper_srts)}** 个 SRT 文件，"
            "可直接翻译，也可在下方额外上传文件。"
        )

    # 来源 B：手动上传
    uploaded = st.file_uploader(
        "上传 SRT 文件（可多选，与 Step 1 结果合并）",
        type=["srt"],
        accept_multiple_files=True,
    )

    # 合并两个来源
    all_files = list(whisper_srts)
    if uploaded:
        all_files += [(f.name, f.read()) for f in uploaded]

    if all_files:
        st.caption(f"共 **{len(all_files)}** 个文件待翻译：" +
                   "、".join(name for name, _ in all_files))

    # 翻译按钮
    if st.button(
        "🚀 开始翻译",
        disabled=not (api_key and all_files),
        type="primary",
    ):
        if not api_key:
            st.error("请在左侧侧边栏填入 DeepL API Key")
            st.stop()

        translator = DeepLTranslator(api_key)
        status = st.empty()
        progress_bar = st.progress(0)

        total_files = len(all_files)
        completed = [0]

        def on_translate_progress(filename, done, total):
            if done == total:
                completed[0] += 1
            pct = completed[0] / total_files
            progress_bar.progress(
                min(pct, 1.0),
                text=f"正在翻译：{filename}（{done}/{total} 条）",
            )

        status.info("翻译进行中，请稍候…")

        try:
            zip_bytes = process_files(
                all_files, translator, progress_callback=on_translate_progress
            )
            progress_bar.progress(1.0, text="翻译完成！")
            status.success(f"✅ 全部 {total_files} 个文件翻译完成")

            st.download_button(
                label="📦 下载翻译后的 ZIP 压缩包",
                data=zip_bytes,
                file_name="translated_subtitles.zip",
                mime="application/zip",
                type="primary",
            )
        except Exception as e:
            status.error(f"❌ 翻译出错：{e}")
            st.exception(e)
