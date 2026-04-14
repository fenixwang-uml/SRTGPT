# SRTGPT — 字幕翻译工具 / Subtitle Translation Tool

批量翻译 SRT 字幕文件，支持多语言，提供 DeepL API 和本地 Ollama 两种翻译引擎。

Batch translate SRT subtitle files across multiple languages using DeepL API or local Ollama.

---

## 环境要求 / Requirements

- Python 3.10+，Windows 10/11
- NVIDIA GPU（使用 Ollama 时推荐 / recommended for Ollama）

---

## 安装 / Installation

    python -m venv SRTGPT
    SRTGPT\Scripts\activate
    pip install -r requirements.txt

Ollama 本地翻译需额外安装：前往 https://ollama.com/download 下载，安装后在系统命令行执行：

For local Ollama translation, download from https://ollama.com/download, then run:

    ollama pull qwen2.5:14b

---

## 启动 / Launch

双击 `启动.bat`，浏览器访问 http://localhost:8502

Double-click `启动.bat`, then open http://localhost:8502 in your browser.

Or manually:

    SRTGPT\Scripts\activate
    streamlit run src\app.py --server.port 8502

---

## 文件结构 / File Structure

    project root/
    ├── src/
    │   ├── app.py                # Streamlit UI
    │   ├── srt_parser.py         # SRT parsing and writing (pysrt)
    │   ├── translator.py         # Translation backends (DeepL / Ollama)
    │   ├── batch_processor.py    # Batch file processing
    │   ├── dedup.py              # Subtitle deduplication
    │   ├── blacklist.py          # Blacklist filtering
    │   ├── languages.py          # Language data and quality tiers
    │   └── config.py             # Local config read/write
    ├── SRTGPT/                   # Virtual environment (not tracked)
    ├── config.json               # Auto-generated local config (not tracked)
    ├── requirements.txt
    ├── LICENSE
    ├── NOTICE.md
    ├── 启动.bat
    ├── .gitignore
    └── README.md

---

## 功能说明 / Features

### 翻译 / Translation（Tab 1）

**上传 SRT 文件 / Upload SRT files**

支持多文件同时上传。如已设置输出路径，上传时自动跳过已存在译文的文件。

Multiple files supported. If an output path is set, files with existing translations are skipped automatically.

**字幕去重 / Deduplication（默认开启 / on by default）**

合并相邻内容相同的字幕条目，可调整最大合并间隔（默认 5 分钟）。

Merges adjacent identical subtitle entries. Max gap is configurable (default 5 minutes).

**用量 / 用时预估 / Usage & time estimation**

DeepL 模式显示账户配额余量；Ollama 模式可测速并预估总用时。

DeepL mode shows account quota; Ollama mode runs a benchmark to estimate total translation time.

**翻译输出路径 / Output path**

每完成一个文件立即保存到指定路径，路径记忆在 config.json。

Each file is saved immediately upon completion. Path is persisted in config.json.

**进度与下载 / Progress & download**

两条进度条分别显示字幕条数和文件数进度。Ollama 模式支持查看模型原始输出和中途中断，完成后提供 ZIP 下载。

Two progress bars show subtitle count and file count. Ollama mode supports raw output inspection and mid-run interruption. ZIP download available on completion.

### 黑名单批处理 / Blacklist Batch Processing（Tab 3）

上传已翻译的中文 SRT 文件，根据侧边栏通配符规则过滤匹配条目，自动重排序号，保存到指定路径或下载 ZIP。

Upload translated SRT files, filter entries matching sidebar wildcard rules, re-index automatically, then save to a path or download as ZIP.

---

## 侧边栏设置 / Sidebar Settings

### 翻译引擎 / Translation Engine

**DeepL API** — 填入 API Key（Free 版末尾为 `:fx`），Key 保存在 config.json。每批 50 条并行发送，Free 版每月 50 万字符免费。注意：Free 版内容可能被 DeepL 用于模型训练，敏感内容请使用 Pro 版。

Enter your API Key (Free tier keys end in `:fx`). Key is saved in config.json. Free tier: 500,000 characters/month. Note: Free tier content may be used by DeepL for model training; use Pro for sensitive content.

**本地 Ollama / Local Ollama** — 无需 Key，数据完全本地。推荐模型 `qwen2.5:14b`，12GB 显存可流畅运行。

No API key required, fully local. Recommended model: `qwen2.5:14b`, runs well with 12GB VRAM.

推理模式 / Inference presets:

- 均衡 / Balanced：ctx 512，批次 8 / batch 8
- 高吞吐 / Throughput：ctx 2048，批次 20 / batch 20
- 自定义 / Custom：手动设置所有参数 / manual parameter control

建议在系统环境变量中添加 `OLLAMA_KEEP_ALIVE = -1`，让模型常驻显存。

Add `OLLAMA_KEEP_ALIVE = -1` to system environment variables to keep the model loaded in VRAM.

### 语言选择 / Language Selection

DeepL 支持 35 种源语言和 36 种目标语言；Ollama 支持 20 种常用语言。选择质量较低的语言对时界面自动显示提示。

DeepL supports 35 source and 36 target languages; Ollama covers 20 common languages. A warning is shown when the selected language pair has limited quality.

### 字幕黑名单 / Subtitle Blacklist

通配符规则，每行一条，保存在 config.json。翻译完成后自动过滤匹配条目并重排序号。

Wildcard rules, one per line, saved in config.json. Matching entries are removed and subtitles re-indexed after translation.

通配符 / Wildcards:

- `*` 匹配任意内容 / matches anything
- `?` 匹配单个字符 / matches one character
- 不区分大小写 / case-insensitive

示例 / Examples：`*广告*`、`请订阅*`、`Translated by ?*`

---

## 本地配置 / Local Config（config.json）

自动生成于根目录，已加入 `.gitignore`。/ Auto-generated at project root, excluded from version control.

| 键 / Key | 说明 / Description |
|----------|-------------------|
| `deepl_api_key` | DeepL API Key |
| `source_lang` | 上次源语言 / Last source language |
| `target_lang` | 上次目标语言 / Last target language |
| `translate_output_dir` | 翻译输出路径 / Translation output path |
| `bl3_output_dir` | 黑名单处理输出路径 / Blacklist output path |
| `dedup_max_gap_s` | 去重最大间隔（秒）/ Dedup max gap (seconds) |
| `blacklist` | 黑名单规则列表 / Blacklist pattern list |

---

## 翻译质量对比 / Quality Comparison

|  | DeepL | Ollama qwen2.5:14b |
|--|-------|--------------------|
| 日/韩/中 → 中文 / JA/KO/ZH → ZH | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 欧洲语言 → 中文 / EU → ZH | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 阿拉伯/俄语 → 中文 / AR/RU → ZH | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 速度 / Speed | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 费用 / Cost | 50万字符/月免费 / 500K chars/month free | 完全免费 / Free |
| 隐私 / Privacy | 上传至服务器 / Uploads to server | 完全本地 / Fully local |

---

## 版权 / License

源代码以 MIT License 发布，详见 LICENSE。/ Source code released under MIT License, see LICENSE.

第三方组件许可及 DeepL 使用限制详见 NOTICE.md。/ Third-party licenses and DeepL usage restrictions in NOTICE.md.
