# NOTICE — 第三方许可与重要声明

本文件说明 SRTGPT 所依赖的第三方组件的许可条款，以及使用本工具时需注意的法律事项。

---

## 一、本项目许可

SRTGPT 的源代码（src/ 目录下所有 .py 文件）以 **MIT License** 发布，详见 LICENSE 文件。

---

## 二、第三方组件

### Streamlit
- 许可：Apache License 2.0
- 来源：https://github.com/streamlit/streamlit
- 版权：Copyright 2019-2024 Streamlit Inc.

### faster-whisper
- 许可：MIT License
- 来源：https://github.com/SYSTRAN/faster-whisper
- 版权：Copyright 2023 SYSTRAN

### Ollama
- 许可：MIT License
- 来源：https://github.com/ollama/ollama
- 版权：Copyright 2023 Ollama

### Qwen2.5 模型（阿里巴巴通义千问）
- 许可：Apache License 2.0
- 来源：https://huggingface.co/Qwen/Qwen2.5-14B-Instruct
- 版权：Copyright 2024 Alibaba Cloud
- 说明：Qwen2.5-14B 以 Apache 2.0 授权，允许商业使用，但须保留原始版权声明。
         使用模型输出时建议注明 "Powered by Qwen"。

### OpenAI Whisper（原始模型权重）
- 许可：MIT License
- 来源：https://github.com/openai/whisper
- 版权：Copyright 2022 OpenAI
- 说明：faster-whisper 使用与 Whisper 兼容的模型权重，该权重以 MIT 许可发布。

---

## 三、DeepL API 使用须知

本工具可选接入 DeepL API 进行翻译。使用前请阅读并遵守 DeepL 的服务条款：
https://www.deepl.com/en/pro-license

**重要限制（摘要，非法律文本，以 DeepL 官方条款为准）：**

1. **禁止创建竞品**：不得将 DeepL API 用于开发以机器翻译为主要目的的竞争性产品、服务或 API。
2. **禁止转售**：不得将 API 访问权限转售或转让给第三方。
3. **禁止训练竞争模型**：不得使用 DeepL API 的输出来开发或训练机器翻译算法。

**Free API 特别说明：**

使用 DeepL API Free 时，DeepL 保留永久存储上传内容及其译文的权利，
并可能将其用于改进自身神经网络模型。
**如需处理敏感或保密内容，请使用 DeepL API Pro（付费版）**，
Pro 版在默认设置下不会存储翻译内容。

本工具将文本发送至 DeepL 服务器进行处理。
使用者须自行确保所翻译内容符合适用的数据保护法律及合同保密义务。

---

## 四、翻译内容版权

本工具仅提供技术辅助翻译，不对翻译结果的版权归属作出任何承诺或保证。

- 翻译原始受版权保护的视频字幕前，请确认你拥有相应权利或已获得授权。
- 本工具生成的译文仅供个人学习和内部使用，未经授权不得用于商业发行。
- 对于因使用本工具翻译受版权保护内容所产生的任何法律责任，作者不承担责任。

---

## 五、免责声明

本软件按"现状"提供，不附带任何形式的明示或暗示保证。
对于因使用本软件导致的任何直接或间接损失，作者不承担法律责任。
