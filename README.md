# SRTGPT — 日文字幕批量翻译工具

日文 MP4 视频 → Whisper 转写 → SRT → 翻译为中文 → ZIP 下载

---

## 环境要求

- Python 3.10+
- NVIDIA 显卡（推荐，Whisper 和 Ollama 均可利用 GPU 加速）
- Windows 10/11

---

## 安装

\`\`\`bash
# 1. 创建并激活虚拟环境
python -m venv SRTGPT
SRTGPT\Scripts\activate

# 2. 安装 Python 依赖
pip install -r src/requirements.txt

# 3. 安装 Ollama（如需本地翻译）
#    前往 https://ollama.com/download 下载 Windows 安装包
#    安装完成后下载模型（在系统命令行，不需要激活 venv）：
ollama pull qwen2.5:14b
\`\`\`

---

## 启动

\`\`\`bash
# 在项目根目录，激活虚拟环境后运行
SRTGPT\Scripts\activate
streamlit run src/app.py
\`\`\`

浏览器自动打开 `http://localhost:8501`

---

## 文件结构

\`\`\`
项目根目录/
├── src/                        # 主程序
│   ├── app.py                  # Streamlit 主界面
│   ├── srt_parser.py           # SRT 解析与写入
│   ├── translator.py           # 翻译后端（DeepL / Ollama）
│   ├── batch_processor.py      # 多文件批量处理与 ZIP 打包
│   ├── whisper_processor.py    # faster-whisper 转写封装
│   ├── config.py               # 本地配置读写模块
│   ├── requirements.txt        # Python 依赖
│   ├── LICENSE                 # MIT License
│   ├── NOTICE.md               # 第三方许可与使用须知
│   └── README.md               # 本文件
│
├── SRTGPT/                     # Python 虚拟环境（不纳入版本控制）
├── config.json                 # 本地配置文件，自动生成（不纳入版本控制）
└── .gitignore
\`\`\`

---

## 功能说明

### Step 1 — MP4 转写 SRT（可选）

扫描内网共享文件夹（UNC 路径）下的所有 MP4 文件，使用 faster-whisper 在本机转写为日文 SRT。

| 设置 | 默认值 | 说明 |
|------|--------|------|
| Whisper 模型 | `large-v3` | 日语识别效果最佳，首次运行自动下载（约 3GB） |
| 运行设备 | `cuda` | 利用 NVIDIA 显卡加速，无显卡改为 `cpu` |
| 内网共享路径 | 上次输入 | UNC 格式，如 `\\Desktop-oco250a\VR2\12` |
| SRT 输出路径 | 上次输入 | 每个文件转写完立即保存，留空则只传给 Step 2 |

转写完成后结果自动传递到 Step 2，同时逐个写入本地磁盘。

### Step 2 — 翻译 SRT

支持两种翻译后端，在左侧边栏切换：

#### DeepL API
- 填入 API Key（Free 版末尾为 `:fx`）
- 每次最多 50 条并行发送，DeepL 内部自动处理上下文
- 翻译前自动查询账户剩余配额及本次预计消耗

#### 本地 Ollama
- 无需 API Key，完全离线，数据不离开本机
- 推荐模型：`qwen2.5:14b`（12GB 显存可流畅运行）
- 翻译策略：8 条/批 + 滑动上下文窗口（前 5 条）
- 提供实测测速与预估总用时（两轮基准测试，自动计算上下文修正系数）
- 支持翻译中途中断，已完成部分仍可下载

### 信息面板

上传文件后自动展开，根据后端显示不同内容：

| DeepL 模式 | Ollama 模式 |
|-----------|------------|
| 各文件字幕条数、字符数 | 各文件字幕条数、字符数 |
| 账户配额余量及翻译后占用比例 | 实测单条耗时及预计总用时 |
| 配额不足时显示警告 | 费用：免费 ✅ |

### 输出

- 文件命名规则：`原文件名_zh.srt`
- 编码：UTF-8
- 打包为 ZIP 下载

---

## 本地配置（config.json）

首次运行后自动在根目录生成，记录上次使用的设置：

\`\`\`json
{
  "whisper_model": "large-v3",
  "whisper_device": "cuda",
  "network_path": "\\\\Desktop-oco250a\\VR2\\12",
  "output_dir": "D:\\Subtitles\\output"
}
\`\`\`

此文件已加入 `.gitignore`，不会被提交到版本控制。

---

## Ollama 说明

Ollama 是独立的系统服务，安装后开机自动在后台运行，监听 `localhost:11434`，无需手动启动。模型文件存储在 `C:\Users\用户名\.ollama\models`，与虚拟环境无关。

建议在 Windows 系统环境变量中添加：

\`\`\`
OLLAMA_KEEP_ALIVE = -1
\`\`\`

模型加载进显存后永久驻留，避免每次翻译前的冷启动等待。

---

## 翻译质量对比

| 维度 | DeepL | Ollama (qwen2.5:14b) |
|------|-------|----------------------|
| 日译中准确度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 上下文连贯性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 速度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 费用 | 免费额度 50 万字符/月 | 完全免费 |
| 数据隐私 | 文本上传至 DeepL 服务器 | 完全本地，数据不出机器 |

---

## 版权与许可

本项目源代码以 **MIT License** 发布，详见 `src/LICENSE`。

第三方组件许可及 DeepL API 使用限制详见 `src/NOTICE.md`。
