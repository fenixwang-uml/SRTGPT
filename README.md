# SRTGPT — Subtitle Translation Tool / 字幕翻译工具

Batch translate SRT subtitle files across multiple languages. Supports DeepL API and local Ollama with advanced prompt-based translation modes.

批量翻译 SRT 字幕文件，支持多语言、DeepL API 和本地 Ollama，含高级 Prompt 翻译模式。

---

## Requirements / 环境要求

- Python 3.10+, Windows 10/11
- NVIDIA GPU recommended for Ollama / 使用 Ollama 时推荐 NVIDIA 显卡

---

## Installation / 安装

    python -m venv SRTGPT
    SRTGPT\Scripts\activate
    pip install -r requirements.txt

For local Ollama translation, download from https://ollama.com/download, then:

    ollama pull qwen2.5:14b

---

## Launch / 启动

Double-click `启动.bat`, then open http://localhost:8502

Or manually / 或手动启动:

    SRTGPT\Scripts\activate
    streamlit run src\app.py --server.port 8502

---

## File Structure / 文件结构

    project root/
    ├── src/
    │   ├── app.py                # Streamlit UI (3 tabs)
    │   ├── translator.py         # DeepL and Ollama backends
    │   ├── prompt_manager.py     # Prompt loading, parsing, tag extraction
    │   ├── batch_processor.py    # Batch file processing
    │   ├── srt_parser.py         # SRT parsing and writing (pysrt)
    │   ├── dedup.py              # Subtitle deduplication
    │   ├── blacklist.py          # Wildcard blacklist filtering
    │   ├── languages.py          # Language data and quality tiers
    │   ├── config.py             # Local config read/write
    │   └── prompts/
    │       ├── standard.txt      # Standard subtitle translation prompt
    │       └── pornify.txt       # Adult content translation prompt
    ├── SRTGPT/                   # Virtual environment (not tracked)
    ├── config.json               # Auto-generated local config (not tracked)
    ├── requirements.txt
    ├── LICENSE
    ├── NOTICE.md
    ├── 启动.bat
    ├── .gitignore
    └── README.md

---

## Features / 功能

### Tab 1 — Translation / 翻译

Standard subtitle translation workflow.

标准字幕翻译流程。

**Upload / 上传**
Multiple SRT files supported. If an output path is set, files with existing translations are automatically skipped.
支持多文件上传，已设置输出路径时自动跳过已存在译文的文件。

**Deduplication / 去重（default on / 默认开启）**
Merges adjacent identical entries. Max gap configurable (default 5 min).
合并相邻重复条目，最大间隔可调（默认 5 分钟）。

**Usage / time estimate / 用量预估**
DeepL: shows account quota and expected character consumption.
Ollama: runs a benchmark to estimate total translation time.
DeepL 显示账户配额；Ollama 实测基准并预估总用时。

**Output path / 输出路径**
Each file saved immediately upon completion. Path persisted in config.json.
每个文件完成后立即保存，路径记忆在 config.json。

**Progress / 进度**
Two progress bars (subtitle count + file count). Real-time ETA: elapsed time, remaining time, and estimated finish time, updated after each batch.
两条进度条（字幕条数 + 文件数）。实时 ETA：已用时、剩余时间、预计完成时刻，每批更新。

Ollama mode: raw model output viewer (latest batch), mid-run interruption with partial download.
Ollama 模式：可查看模型原始输出，支持中断并下载已完成部分。

---

### Tab 2 — Advanced Mode / 高级模式

Ollama-only. Uses external prompt files with tone selection and cross-batch scene context.
仅限 Ollama。使用外置 Prompt 文件，支持风格选择和跨批次场景上下文。

**Tone selection / 风格选择**
- `standard` — Professional subtitle translation / 专业字幕翻译
- `pornify` — Adult content translation with explicit language / 成人内容翻译
- Custom `.txt` files in `src/prompts/` are auto-detected / 自定义 .txt 文件自动检测

**Prompt format / Prompt 格式**
Files use a three-section structure:
文件采用三段结构：

    ### prompt           — User message header
    ### instructions     — System prompt (supports {source_lang} / {target_lang})
    ### retry_instructions — Retry prompt on format failure

**Scene context / 场景上下文**
Each batch extracts a `<scene>` tag from the model output and passes it to the next batch as context, replacing the sliding window approach. Displayed live in the UI.
每批从模型输出提取 `<scene>` 标签传给下一批作为上下文，替代滑动窗口。实时显示在界面。

All Tab 1 preprocessing (dedup, blacklist, duplicate file check, output path, ETA) is included.
包含全部 Tab 1 预处理功能（去重、黑名单、重复检查、输出路径、ETA）。

---

### Tab 3 — Blacklist Batch Processing / 黑名单批处理

Upload translated `_zh.srt` files. Entries matching sidebar blacklist rules are removed and subtitles re-indexed. Save to a path or download as ZIP.
上传已翻译的 `_zh.srt` 文件，过滤黑名单匹配条目并重排序号，保存到指定路径或下载 ZIP。

---

## Sidebar Settings / 侧边栏设置

### Translation Engine / 翻译引擎

**DeepL API** — Enter API Key (Free tier keys end in `:fx`). Key saved in config.json. 500,000 characters/month free. Note: Free tier content may be used by DeepL for model training.
填入 API Key（Free 版末尾为 `:fx`），Key 保存在 config.json，每月 50 万字符免费。Free 版内容可能被 DeepL 用于训练。

**Local Ollama** — No API key, fully local. Recommended: `qwen2.5:14b` (12GB VRAM).
无需 Key，完全本地。推荐 `qwen2.5:14b`（12GB 显存）。

Inference presets / 推理模式:
- Balanced: ctx 2048, batch 10
- Throughput: ctx 4096, batch 20
- Custom: manual parameter control with automatic batch size clamping to prevent context overflow

Batch size is automatically capped based on `num_ctx` to prevent context overflow.
批次大小根据 `num_ctx` 自动上限，防止上下文溢出。

Add `OLLAMA_KEEP_ALIVE = -1` to system environment variables to keep the model loaded in VRAM.
在系统环境变量中添加 `OLLAMA_KEEP_ALIVE = -1`，让模型常驻显存。

### Language Selection / 语言选择

DeepL: 35 source / 36 target languages. Ollama: 20 common languages.
A warning is shown for language pairs with limited quality.
DeepL 支持 35 种源语言和 36 种目标语言；Ollama 支持 20 种常用语言。质量较低的语言对会显示警告。

### Blacklist / 黑名单

Wildcard rules, one per line, saved in config.json. Applied after translation (Tab 1 & 2) and as standalone batch processing (Tab 3).
通配符规则，每行一条，保存在 config.json。翻译后自动过滤（Tab 1 & 2），也可单独批量处理（Tab 3）。

Wildcards / 通配符: `*` = anything, `?` = one character, case-insensitive.
示例: `*广告*`, `请订阅*`, `Translated by ?*`

---

## Local Config / 本地配置（config.json）

Auto-generated at project root, excluded from version control.
自动生成于根目录，已加入 `.gitignore`。

| Key / 键 | Description / 说明 |
|----------|-------------------|
| `deepl_api_key` | DeepL API Key |
| `source_lang` | Last source language / 上次源语言 |
| `target_lang` | Last target language / 上次目标语言 |
| `translate_output_dir` | Tab 1 output path / 翻译输出路径 |
| `adv_output_dir` | Tab 2 output path / 高级模式输出路径 |
| `bl3_output_dir` | Tab 3 output path / 黑名单处理输出路径 |
| `dedup_max_gap_s` | Dedup max gap in seconds / 去重最大间隔（秒）|
| `blacklist` | Blacklist pattern list / 黑名单规则列表 |
| `adv_tone` | Last selected tone / 上次选择的翻译风格 |
| `custom_prompt_path` | Custom prompt file path / 自定义 Prompt 文件路径 |

---

## Translation Quality / 翻译质量对比

|  | DeepL | Ollama qwen2.5:14b |
|--|-------|--------------------|
| JA/KO/ZH → ZH 日韩中→中文 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| EU langs → ZH 欧洲语言→中文 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| AR/RU → ZH 阿拉伯/俄→中文 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Speed / 速度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Cost / 费用 | 500K chars/month free | Free / 完全免费 |
| Privacy / 隐私 | Uploads to server / 上传服务器 | Fully local / 完全本地 |

---

## License / 版权

Source code released under MIT License — see LICENSE.
Third-party licenses and DeepL usage restrictions — see NOTICE.md.

源代码以 MIT License 发布，详见 LICENSE。第三方许可及 DeepL 使用限制详见 NOTICE.md。
