"""提示词模板加载器 — 从 prompts/ 目录读取 .txt 文件。"""

import os

_PROMPT_DIR = os.path.dirname(__file__)


def load_prompt(name: str) -> str:
    """加载提示词模板文件。

    Args:
        name: 不含 .txt 扩展名的文件名（如 "template_agent"）。

    Returns:
        提示词模板字符串。
    """
    path = os.path.join(_PROMPT_DIR, f"{name}.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
