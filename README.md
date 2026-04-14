# SRTGPT — 日文字幕批量翻译工具

上传日文 SRT 字幕文件，通过 DeepL API 或本地 Ollama 模型翻译为中文，支持去重优化、本地保存和批量处理。

---

## 环境要求

- Python 3.10+，Windows 10/11
- NVIDIA 显卡（使用 Ollama 本地翻译时推荐）

---

## 安装与启动

    python -m venv SRTGPT
    SRTGPT\Scripts\activate
    pip install streamlit ollama
    streamlit run src/app.py

浏览器自动打开 http://localhost:8501

Ollama 本地翻译需额外安装：前往 https://ollama.com/download 下载，安装后在系统命令行执行 `ollama pull qwen2.5:14b`（约 9GB）。Ollama 安装后开机自动后台运行，无需手动启动。

---

## 文件结构

    项目根目录/
    ├── src/
    │   ├── app.py                # Streamlit 主界面
    │   ├── srt_parser.py         # SRT 解析与写入
    │   ├── translator.py         # 翻译后端（DeepL / Ollama）
    │   ├── batch_processor.py    # 多文件处理与保存
    │   ├── dedup.py              # 字幕去重模块
    │   ├── config.py             # 本地配置读写
    │   ├── requirements.txt
    │   ├── LICENSE
    │   └── NOTICE.md
    ├── SRTGPT/                   # 虚拟环境（不纳入版本控制）
    ├── config.json               # 自动生成的本地配置（不纳入版本控制）
    ├── .gitignore
    └── README.md

---

## 使用流程

**1. 选择翻译引擎**（左侧边栏）

DeepL API 或本地 Ollama，详见下方说明。

**2. 上传 SRT 文件**

支持多文件同时上传。如已设置翻译输出路径，上传时自动检查是否存在同名译文，存在则跳过，避免重复翻译。

**3. 字幕去重（可选，默认开启）**

合并相邻内容相同的字幕条目。可调整最大合并间隔（默认 5 分钟），设置保存在 config.json。

**4. 确认用量信息**

- DeepL 模式：显示各文件字幕条数、字符数、账户剩余配额及翻译后占用比例
- Ollama 模式：显示字幕条数，可点击「测速并预估用时」实测当前模型速度

**5. 设置输出路径（可选）**

填写本地路径后，每完成一个文件立即保存，无需等待全部完成。路径保存在 config.json，下次启动自动填入。

**6. 开始翻译**

两条进度条分别显示字幕条数进度和文件数进度。Ollama 模式下可展开「模型原始输出」查看最新一批的原始响应，可随时中断并下载已完成部分。

**7. 下载**

翻译完成后提供 ZIP 下载，包含所有 `原文件名_zh.srt` 文件（UTF-8 编码）。

---

## 翻译引擎

### DeepL API

填入 API Key（Free 版末尾为 `:fx`），Key 保存在 config.json 供下次使用。每批 50 条并行发送，DeepL 内部自动处理上下文连贯。Free 版每月 50 万字符免费。

注意：使用 DeepL API Free 时，上传的文本内容可能被 DeepL 用于模型训练。如需处理敏感内容，请使用 Pro 版。

### 本地 Ollama

无需 API Key，完全离线，数据不离开本机。推荐模型 `qwen2.5:14b`，12GB 显存可流畅运行。

翻译策略：每批 8 条（高吞吐模式 20 条）+ 前 5 条滑动上下文窗口，兼顾速度与连贯性。

提供三种推理模式：

- 均衡模式：ctx 512，批次 8，适合日常使用
- 高吞吐模式：ctx 2048，批次 20，GPU 利用率更高
- 自定义模式：手动设置所有推理参数，仅供高级调试

建议在系统环境变量中添加 `OLLAMA_KEEP_ALIVE = -1`，让模型常驻显存，避免每次冷启动等待。

---

## 本地配置（config.json）

首次运行后自动在根目录生成，保存以下设置：

- `deepl_api_key`：DeepL API Key
- `translate_output_dir`：翻译结果保存路径
- `dedup_max_gap_s`：去重最大间隔（秒）

已加入 `.gitignore`，不会被提交到版本控制。

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
