"""Reflection Engine — 分析验证失败原因，生成修正策略。

区别于 Validation（只指出问题），Reflection 生成具体的、可操作的
extraction_hints，注入 Extraction Agent 的下一次调用。降级方案基于规则生成。
"""

import json
from typing import List

from agent.state import ExtractionState
from agent.tools.llm_utils import call_llm


def reflection_engine(state: ExtractionState) -> dict:
    """分析验证问题 → 生成 extraction_hints。"""
    issues = state.get("validation_issues", [])
    current_rows = state.get("current_rows", [])
    columns = state.get("columns", [])
    pdf_text = state.get("pdf_text", "")

    if not issues:
        return {
            "extraction_hints": "",
            "reflection_rounds": state.get("reflection_rounds", 0) + 1,
        }

    col_names = [c["col_name"] for c in columns]

    try:
        hints = _llm_generate_hints(issues, current_rows, col_names, pdf_text)
    except Exception:
        hints = _fallback_hints(issues)

    return {
        "extraction_hints": hints,
        "reflection_rounds": state.get("reflection_rounds", 0) + 1,
    }


def _llm_generate_hints(
    issues: List[dict], rows: List[dict], col_names: List[str], pdf_text: str
) -> str:
    """使用 LLM 生成具体的修正指引。"""
    issues_text = _format_issues(issues)

    prompt = f"""你是数据提取策略分析师。以下问题在验证中被发现：

## 问题
{issues_text}

## 当前数据
{json.dumps(rows, ensure_ascii=False)[:1500]}

## 模板列
{col_names}

生成修正指引（编号列表），每条必须具体且可操作：
1. 指出应重读 PDF 的哪个段落/表/图
2. 对异常值给出可能原因和正确值范围
3. 对遗漏数据指出可能位置
4. 对单位不一致给出统一建议

直接返回纯文本指引。"""

    system = "你是数据提取策略分析师。生成具体的修正指引。"
    response = call_llm(prompt, system=system)
    return response.strip()


def _format_issues(issues: List[dict]) -> str:
    """格式化问题列表为可读文本。"""
    lines = []
    for i, issue in enumerate(issues, 1):
        level = issue.get("level", "")
        col = issue.get("column", "")
        row_idx = issue.get("row_index", -1)
        desc = issue.get("description", "")
        sev = issue.get("severity", "")

        row_info = f"第{row_idx + 1}行" if row_idx >= 0 else "全局"
        col_info = f"列{col}" if col else ""
        location = f"{row_info} {col_info}".strip()

        lines.append(f"{i}. [{sev.upper()}] [{level}] {location}: {desc}")

    return "\n".join(lines)


def _fallback_hints(issues: List[dict]) -> str:
    """降级方案：基于规则生成简单指引，不依赖 LLM。"""
    hints = []
    for i, issue in enumerate(issues, 1):
        level = issue.get("level", "")
        desc = issue.get("description", "")

        if level == "plausibility":
            hints.append(
                f"{i}. {desc}。请重新检查 PDF 中对应的数值，"
                f"确认小数点和单位是否正确。"
            )
        elif level == "completeness":
            hints.append(
                f"{i}. {desc}。请扫描 PDF 全文，查找是否遗漏了该数据。"
            )
        elif level == "traceability":
            hints.append(
                f"{i}. {desc}。请在 PDF 中找到该数据的来源表/图并标注。"
            )
        elif level == "consistency":
            hints.append(
                f"{i}. {desc}。请统一所有行的单位和格式。"
            )
        else:
            hints.append(f"{i}. {desc}")

    return "\n".join(hints)
