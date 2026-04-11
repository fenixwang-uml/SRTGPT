# SRTGPT — 日文字幕批量翻译工具

上传日文 SRT 字幕文件 → DeepL 或本地 Ollama 翻译为中文 → ZIP 下载

---

## 环境要求

- Python 3.10+，Windows 10/11
- NVIDIA 显卡（Ollama 本地翻译推荐）

---

## 安装与启动

    python -m venv SRTGPT
    SRTGPT\Scripts\activate
    pip install -r src/requirements.txt
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
    │   ├── config.py             # 本地配置读写
    │   ├── requirements.txt
    │   ├── LICENSE
    │   └──NOTICE.md
    │   
    ├── SRTGPT/                   # 虚拟环境（不纳入版本控制）
    ├── config.json               # 自动生成的本地配置（不纳入版本控制）
    ├── .gitignore
    └── README.md
---

## 使用说明

上传一个或多个 SRT 文件，在左侧选择翻译后端，确认用量信息后点击开始翻译，完成后下载 ZIP。

**DeepL API** — 填入 API Key（Free 版末尾为 `:fx`）。每批 50 条并行发送，DeepL 内部自动处理上下文连贯。翻译前显示本次预计字符消耗和账户剩余配额。

**本地 Ollama** — 无需 Key，数据不离开本机。每批 8 条 + 前 5 条滑动上下文窗口。提供实测测速和预估总用时，支持中途中断并下载已完成部分。

输出文件命名为 `原文件名_zh.srt`，UTF-8 编码，打包为 ZIP。

---

## 本地配置

config.json 自动生成于项目根目录，目前不存储任何默认值，仅作为未来扩展预留。已加入 `.gitignore`。

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
