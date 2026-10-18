"""LLM 调用工具 — 封装 LLM 调用、JSON 解析、token 计数。"""

import json
import os
import re
from typing import Any

from langchain_openai import ChatOpenAI

from config.settings import settings


def get_llm(response_format: str = "json_object") -> ChatOpenAI:
    """获取配置好的 LLM 实例（使用 DeepSeek API，兼容 OpenAI 协议）。

    API key 优先从环境变量实时读取（支持 Streamlit 侧边栏注入），
    回退到 settings 模块的初始值。

    Args:
        response_format: 响应格式（"json_object" 或 "text"）。

    Returns:
        ChatOpenAI 实例，指向 DeepSeek API。
    """
    # 实时读取环境变量 — Streamlit 侧边栏可能在导入后才注入
    api_key = os.getenv("DEEPSEEK_API_KEY") or settings.deepseek_api_key
    base_url = os.getenv("DEEPSEEK_BASE_URL") or settings.deepseek_base_url
    model = os.getenv("MODEL_NAME") or settings.model_name

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        model_kwargs={"response_format": {"type": response_format}},
    )


def call_llm(prompt: str, system: str = "") -> str:
    """调用 LLM 并返回文本内容。

    Args:
        prompt: 用户提示词。
        system: 系统提示词（可选）。

    Returns:
        LLM 响应的文本内容。
    """
    llm = get_llm(response_format="text")
    messages = []
    if system:
        messages.append(("system", system))
    messages.append(("human", prompt))
    response = llm.invoke(messages)
    return response.content


def parse_json_response(response: str) -> Any:
    """从 LLM 响应中解析 JSON，含多层回退策略。

    LLM 返回的 JSON 可能被包裹在 markdown 代码块中，或包含尾部逗号等
    非法 JSON。此函数采用多层回退策略确保成功解析。

    Args:
        response: LLM 的原始响应文本。

    Returns:
        解析后的 Python 对象（dict 或 list）。

    Raises:
        ValueError: 所有解析策略均失败。
    """
    # 尝试 1: 直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 尝试 2: 提取 markdown 代码块中的 JSON
    code_block_match = re.search(
        r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL
    )
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试 3: 查找第一个 [ 或 { 到最后一个 ] 或 } 之间的内容
    for open_char, close_char in [("[", "]"), ("{", "}")]:
        start_idx = response.find(open_char)
        end_idx = response.rfind(close_char)
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(response[start_idx:end_idx + 1])
            except json.JSONDecodeError:
                pass

    # 尝试 4: 修复常见 JSON 错误（尾部逗号）
    cleaned = re.sub(r",\s*([}\]])", r"\1", response)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    raise ValueError(f"无法从 LLM 响应中解析 JSON: {response[:200]}...")


def count_tokens(text: str) -> int:
    """估算文本的 token 数量（粗略：3 字符 ≈ 1 token）。

    Args:
        text: 输入文本。

    Returns:
        估算的 token 数量。
    """
    return len(text) // 3
