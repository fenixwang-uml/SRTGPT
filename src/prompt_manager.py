"""
Prompt 管理模块
负责加载外置 prompt 文件，解析三段结构，替换语言占位符，
以及从模型输出中提取 <scene> / <summary> 标签内容。

文件格式（src/prompts/{tone}.txt）：
    ### prompt
    用户消息模板（含 [ to language] 占位符）

    ### instructions
    System prompt 正文（含 {source_lang} / {target_lang} 占位符）

    ### retry_instructions
    翻译失败时的重试提示
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROMPTS_DIR = Path(__file__).parent / "prompts"

# 内置兜底字符串（文件缺失时使用）
_FALLBACK_INSTRUCTIONS = (
    "You are a professional subtitle translator. "
    "Translate the provided subtitles from {{source_lang}} into {{target_lang}}. "
    "Output only the translation in [N] format, one line per entry. "
    "Do not add any markdown or extra formatting."
)

_FALLBACK_RETRY = (
    "Please translate again. Output every line separately in [N] format. "
    "Do not skip or merge lines."
)


@dataclass
class PromptSet:
    """解析后的完整 prompt 集合"""
    instructions: str          # system prompt
    prompt_header: str         # 用户消息前缀（来自 ### prompt 段）
    retry_instructions: str    # 重试 prompt
    tone: str = "standard"
    raw_sections: dict = field(default_factory=dict)


def _parse_sections(text: str) -> dict:
    """
    将 ### section_name 格式的文件解析为 {section_name: content} 字典。
    """
    sections = {}
    current_key = None
    current_lines = []

    for line in text.splitlines():
        if line.startswith("### "):
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = line[4:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _substitute_langs(text: str, source_lang: str, target_lang: str) -> str:
    """替换 {source_lang} / {target_lang} 占位符"""
    return text.replace("{source_lang}", source_lang).replace("{target_lang}", target_lang)


def load_prompt(
    tone: str = "standard",
    source_lang: str = "日语",
    target_lang: str = "简体中文",
    custom_path: Optional[str] = None,
) -> PromptSet:
    """
    加载并解析 prompt 文件。

    优先级：
    1. custom_path（用户指定的文件）
    2. src/prompts/{tone}.txt（内置）
    3. 硬编码兜底字符串
    """
    raw_text = None

    # 1. 用户自定义文件
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            try:
                raw_text = p.read_text(encoding="utf-8")
            except Exception:
                pass

    # 2. 内置 prompts 目录
    if raw_text is None:
        builtin = PROMPTS_DIR / f"{tone}.txt"
        if builtin.exists():
            try:
                raw_text = builtin.read_text(encoding="utf-8")
            except Exception:
                pass

    # 3. 兜底
    if raw_text is None:
        return PromptSet(
            instructions=_substitute_langs(_FALLBACK_INSTRUCTIONS, source_lang, target_lang),
            prompt_header=f"Please translate the following subtitles to {target_lang}.",
            retry_instructions=_FALLBACK_RETRY,
            tone=tone,
        )

    sections = _parse_sections(raw_text)

    instructions = _substitute_langs(
        sections.get("instructions", _FALLBACK_INSTRUCTIONS),
        source_lang, target_lang,
    )
    retry = _substitute_langs(
        sections.get("retry_instructions", _FALLBACK_RETRY),
        source_lang, target_lang,
    )

    # 处理 prompt 段的占位符 [ for movie] / [ to language]
    prompt_header = sections.get("prompt", f"Please translate the following subtitles to {target_lang}.")
    prompt_header = re.sub(r'\[\s*for\s+movie\s*\]', '', prompt_header)
    prompt_header = re.sub(r'\[\s*to\s+language\s*\]', f'to {target_lang}', prompt_header)
    prompt_header = prompt_header.strip()

    return PromptSet(
        instructions=instructions,
        prompt_header=prompt_header,
        retry_instructions=retry,
        tone=tone,
        raw_sections=sections,
    )


def extract_tags(raw: str) -> dict:
    """
    从模型原始输出中提取 <summary> 和 <scene> 标签内容。
    返回 {"summary": str, "scene": str, "clean": str}
    clean 是去掉标签后的纯翻译文本。
    """
    summary_match = re.search(r'<summary>(.*?)</summary>', raw, re.DOTALL | re.IGNORECASE)
    scene_match   = re.search(r'<scene>(.*?)</scene>',   raw, re.DOTALL | re.IGNORECASE)

    summary = summary_match.group(1).strip() if summary_match else ""
    scene   = scene_match.group(1).strip()   if scene_match   else ""

    # 去掉标签及其内容，得到纯翻译行
    clean = re.sub(r'<summary>.*?</summary>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<scene>.*?</scene>',     '', clean, flags=re.DOTALL | re.IGNORECASE)

    # 同时去掉可能遗留的代码块标记
    clean = re.sub(r'```[a-zA-Z]*\n?', '', clean)
    clean = clean.strip()

    return {"summary": summary, "scene": scene, "clean": clean}


def list_available_tones() -> list:
    """返回 prompts/ 目录下所有可用的 tone 名称"""
    if not PROMPTS_DIR.exists():
        return ["standard"]
    return sorted(p.stem for p in PROMPTS_DIR.glob("*.txt"))
