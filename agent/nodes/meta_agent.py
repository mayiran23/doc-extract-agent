"""Meta Agent — 从检测报告 PDF 文本提取报告元信息。

处理逻辑：
1. LLM 从报告前 4000 字符提取报告编号、检测机构、样品信息、检测日期、依据标准
2. 对报告编号做格式校验，不合规范的在摘要中标记待核对
3. 组装成供结果表使用的一行元信息摘要
"""

import json
import re

from agent.state import ExtractionState
from agent.tools.llm_utils import call_llm

# 常见报告编号形态：字母/汉字前缀 + 年份 + 流水号，允许 - 或 / 分隔
REPORT_NO_RE = re.compile(r"^[A-Za-z\u4e00-\u9fa5]{1,8}[-/]?\d{4,}[-/]?\w*$")

FIELDS = [
    ("report_no", "报告编号"),
    ("institution", "检测机构"),
    ("sample_id", "样品编号"),
    ("sample_name", "样品名称"),
    ("test_date", "检测日期"),
    ("standard_basis", "依据标准"),
    ("conclusion", "总体结论"),
]


def meta_agent(state: ExtractionState) -> dict:
    """从 PDF 文本提取报告元信息并生成摘要。"""
    pdf_text = state.get("pdf_text", "")

    if not pdf_text:
        return {"citation": ""}

    metadata = _extract_metadata(pdf_text[:4000])
    return {"citation": _format_summary(metadata)}


def _extract_metadata(text_head: str) -> dict:
    """使用 LLM 从报告开头提取元信息。"""
    prompt = f"""从以下检测报告文本的开头部分提取报告元信息，以JSON格式返回：

{text_head}

返回JSON格式（缺失的字段用空字符串）：
{{
    "report_no": "报告编号",
    "institution": "检测机构名称",
    "sample_id": "样品编号",
    "sample_name": "样品名称",
    "test_date": "检测日期（YYYY-MM-DD）",
    "standard_basis": "依据标准（如 GB/T 5750-2023）",
    "conclusion": "报告总体结论"
}}

只返回JSON，不要其他内容。"""

    system = "你是一名检测报告元信息提取专家。只返回JSON。"
    try:
        metadata = json.loads(call_llm(prompt, system=system))
    except Exception:
        return {}

    return metadata if isinstance(metadata, dict) else {}


def _format_summary(metadata: dict) -> str:
    """把元信息组装成一行可读摘要。"""
    if not metadata:
        return ""

    parts = []
    for key, label in FIELDS:
        val = str(metadata.get(key, "") or "").strip()
        if val:
            parts.append(f"{label}: {val}")

    report_no = str(metadata.get("report_no", "") or "").strip()
    if report_no and not REPORT_NO_RE.match(report_no):
        parts.append("（报告编号格式待核对）")

    return "；".join(parts)
