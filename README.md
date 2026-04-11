# SRTGPT — 日文字幕批量翻译工具

日文 MP4 → Whisper 转写 → SRT → 翻译为中文 → ZIP 下载

---

## 环境要求

- Python 3.10+，Windows 10/11
- NVIDIA 显卡（推荐，Whisper 和 Ollama 均可 GPU 加速）

---

## 安装与启动

在项目根目录创建虚拟环境并安装依赖：

    python -m venv SRTGPT
    SRTGPT\Scripts\activate
    pip install -r src/requirements.txt

启动：

    streamlit run src/app.py

浏览器自动打开 http://localhost:8501

Ollama 本地翻译需额外安装：前往 https://ollama.com/download 下载，安装后在系统命令行执行 `ollama pull qwen2.5:14b`（约 9GB）。

---

## 文件结构

    项目根目录/
    ├── src/
    │   ├── app.py                # Streamlit 主界面
    │   ├── srt_parser.py         # SRT 解析与写入
    │   ├── translator.py         # 翻译后端（DeepL / Ollama）
    │   ├── batch_processor.py    # 多文件处理与 ZIP 打包
    │   ├── whisper_processor.py  # faster-whisper 转写封装
    │   ├── config.py             # 本地配置读写
    │   ├── requirements.txt
    │   ├── LICENSE
    │   ├── NOTICE.md
    │   └── README.md
    ├── SRTGPT/                   # 虚拟环境（不纳入版本控制）
    ├── config.json               # 自动生成的本地配置（不纳入版本控制）
    └── .gitignore

---

## 使用说明

### Step 1 — MP4 转写 SRT（可选）

填入内网共享路径（如 `\\Desktop-oco250a\VR2\12`），扫描到 MP4 文件后点击开始转写。每个文件转写完立即保存到指定的本地输出路径，同时传给 Step 2。

默认使用 large-v3 模型 + cuda，首次运行自动从 Hugging Face 下载模型（约 3GB）。

### Step 2 — 翻译 SRT

在侧边栏选择翻译后端：

**DeepL API** — 填入 API Key（Free 版末尾为 `:fx`）。每批 50 条并行发送，翻译前显示本次预计字符消耗和账户剩余配额。

**本地 Ollama** — 无需 Key，数据不离开本机。每批 8 条 + 前 5 条滑动上下文窗口。提供实测测速和预估总用时，支持中途中断并下载已完成部分。

输出文件命名为 `原文件名_zh.srt`，UTF-8 编码，打包为 ZIP 下载。

---

## 本地配置

首次运行后在根目录自动生成 config.json，记录上次使用的 Whisper 模型、设备、网络路径和输出路径，下次启动自动还原。

---

## Ollama 说明

Ollama 安装后开机自动后台运行，无需手动启动。建议在系统环境变量中添加 `OLLAMA_KEEP_ALIVE = -1`，让模型常驻显存，避免每次冷启动等待。

---

## 翻译质量对比

|  | DeepL | Ollama qwen2.5:14b |
|--|-------|--------------------|
| 日译中准确度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 上下文连贯性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 速度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 费用 | 50 万字符/月免费 | 完全免费 |
| 数据隐私 | 上传至 DeepL 服务器 | 完全本地 |

---

## 版权

源代码以 MIT License 发布，详见 src/LICENSE。第三方组件许可及 DeepL 使用限制详见 src/NOTICE.md。
