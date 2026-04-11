# 日文 SRT 字幕批量翻译工具

DeepL API + Streamlit 网页界面，将日文 .srt 字幕批量翻译为中文。

## 依赖

- Python 3.10+
- 仅需安装 Streamlit（其余均为标准库）

## 安装与运行

```bash
# 1. 进入项目目录
cd srt_translator

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动网页
streamlit run app.py
```

浏览器会自动打开 http://localhost:8501

## 目录结构

```
srt_translator/
├── app.py              # Streamlit 主界面
├── srt_parser.py       # SRT 解析与写入
├── translator.py       # DeepL API 封装（批量翻译）
├── batch_processor.py  # 多文件处理与 ZIP 打包
├── requirements.txt
└── README.md
```

## 注意事项

- Free 版 API Key 末尾为 `:fx`，程序会自动选择对应域名
- 每月免费额度：500,000 字符
- 字幕文件支持 UTF-8 / UTF-8-BOM / Shift-JIS 编码自动检测
- 输出文件命名规则：`原文件名_zh.srt`，统一 UTF-8 编码
