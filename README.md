# SRTGPT — 日文字幕批量翻译工具

日文 MP4 视频 → Whisper 转写 → SRT → 翻译为中文 → ZIP 下载

---

## 环境要求

- Python 3.10+
- NVIDIA 显卡（推荐，Whisper 和 Ollama 均可利用 GPU 加速）
- Windows 10/11

---

## 安装

```bash
# 1. 创建并激活虚拟环境
python -m venv SRTGPT
SRTGPT\Scripts\activate

# 2. 安装 Python 依赖
pip install -r src/requirements.txt

# 3. 安装 Ollama（如需本地翻译）
#    前往 https://ollama.com/download 下载 Windows 安装包
#    安装完成后下载模型（在系统命令行，不需要 venv）：
ollama pull qwen2.5:14b
```

---

## 启动

```bash
# 激活虚拟环境后运行
streamlit run src/app.py
```

浏览器自动打开 `http://localhost:8501`

---

## 功能说明

### Step 1 — MP4 转写 SRT（可选）

扫描内网共享文件夹（UNC 路径，如 `\\192.168.1.10\media\videos`）下的所有 MP4 文件，使用 faster-whisper 在本机转写为日文 SRT。

| 设置 | 说明 |
|------|------|
| Whisper 模型 | 推荐 `medium`，日语识别效果最佳 |
| 运行设备 | 有 NVIDIA 显卡选 `cuda`，速度提升显著 |

转写完成后结果自动传递到 Step 2。

### Step 2 — 翻译 SRT

支持两种翻译后端，在左侧边栏切换：

#### DeepL API
- 填入 API Key（Free 版末尾为 `:fx`）
- 每次最多 50 条打包发送，自动处理上下文连贯
- 自动查询账户剩余配额，翻译前显示本次预计消耗

#### 本地 Ollama
- 无需 API Key，完全离线运行
- 推荐模型：`qwen2.5:14b`（12GB 显存可流畅运行）
- 翻译策略：8 条字幕为一批 + 滑动上下文窗口（前 5 条），兼顾速度与连贯性
- 点击「测速并预估用时」进行实测，修正系数由两轮基准测试自动计算
- 翻译过程中可随时点击「中断翻译」，已完成部分仍可下载

### 信息面板

上传文件后自动展开，根据当前后端显示：

- **DeepL 模式**：各文件字幕条数、字符数、账户配额余量及翻译后占用比例
- **Ollama 模式**：各文件字幕条数、字符数、实测单条耗时及预计总用时

### 输出

- 文件命名规则：`原文件名_zh.srt`
- 编码：UTF-8
- 打包为 ZIP 下载

---

## 文件结构

```
src/
├── app.py                # Streamlit 主界面
├── srt_parser.py         # SRT 解析与写入（自动检测 UTF-8 / Shift-JIS）
├── translator.py         # 翻译后端（DeepLTranslator / OllamaTranslator）
├── batch_processor.py    # 多文件批量处理与 ZIP 打包
├── whisper_processor.py  # faster-whisper 转写封装
├── requirements.txt      # Python 依赖
└── README.md
```

---

## Ollama 说明

Ollama 是独立的系统服务，开机后自动在后台运行，监听 `localhost:11434`，无需手动启动。模型文件存储在 `C:\Users\用户名\.ollama\models`，与 Python 虚拟环境无关。

建议在 Windows 系统环境变量中添加：

```
OLLAMA_KEEP_ALIVE = -1
```

模型加载进显存后永久驻留，避免每次翻译前的冷启动等待。

---

## 翻译质量对比

| 维度 | DeepL | Ollama (qwen2.5:14b) |
|------|-------|----------------------|
| 日译中准确度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 上下文连贯性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 速度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 费用 | 免费额度 50万字符/月 | 完全免费 |
| 隐私 | 文本上传至 DeepL 服务器 | 完全本地 |
