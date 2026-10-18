"""Validation Engine — 四级数据质量检查（规则 + LLM 双重检查）。"""

import json
from typing import List

from agent.state import ExtractionState
from agent.tools.llm_utils import call_llm


def validation_engine(state: ExtractionState) -> dict:
    """执行四级检查并返回结果。"""
    current_rows = state.get("current_rows", [])
    columns = state.get("columns", [])
    pdf_text = state.get("pdf_text", "")

    if not current_rows:
        return {
            "validation_passed": True,
            "validation_issues": [],
            "validation_detail": "无数据可验证",
        }

    # 规则检查（确定性，不调用 LLM，速度快）
    rule_issues = _rule_check(current_rows, columns)

    # 深度 LLM 检查：仅在规则检查发现问题时才触发，且限制轮次
    llm_issues = []
    has_rule_errors = any(i.get("severity") == "error" for i in rule_issues)
    if has_rule_errors and state.get("reflection_rounds", 0) < 2:
        try:
            llm_issues = _llm_check(current_rows, columns, pdf_text)
        except Exception:
            pass

    all_issues = rule_issues + llm_issues
    has_errors = any(i.get("severity") == "error" for i in all_issues)

    return {
        "validation_passed": not has_errors,
        "validation_issues": all_issues,
        "validation_detail": _build_detail(all_issues, not has_errors),
    }


def _rule_check(rows: List[dict], columns: List[dict]) -> List[dict]:
    """基于规则的快速检查。"""
    issues = []
    col_names = [c["col_name"] for c in columns]

    for i, row in enumerate(rows):
        values = row.get("values", {})

        # Completeness: 填充率过低的警告
        empty = sum(1 for cn in col_names if not values.get(cn))
        if empty > len(col_names) * 0.8:
            issues.append({
                "level": "completeness", "column": "", "row_index": i,
                "description": f"第{i+1}行超过80%的列未填充数据",
                "severity": "warning",
            })

        # Plausibility: 数值型字段非负 + 期望范围
        for col in columns:
            cn = col.get("col_name", "")
            val = values.get(cn, "")
            if not val:
                continue

            num = _to_float(val)
            if num is None:
                continue

            # 检测值/限值/金额类字段不允许为负
            if col.get("semantic_type") in ("measured_value", "limit_value") and num < 0:
                issues.append({
                    "level": "plausibility", "column": cn, "row_index": i,
                    "description": f"{cn} 为负值 ({num})，检测值不应为负",
                    "severity": "error",
                })
                continue

            # 列定义里给了合理范围就校验（如 "0-100"、"0.001-9999"）
            rng = col.get("expected_range", "")
            if rng and not _in_range(num, rng):
                issues.append({
                    "level": "plausibility", "column": cn, "row_index": i,
                    "description": f"{cn} 的值 {num} 超出合理范围 ({rng})",
                    "severity": "error",
                })

        # Traceability: 有数据但无来源
        if any(values.get(cn) for cn in col_names):
            if not row.get("source_table") and not row.get("source_figure"):
                issues.append({
                    "level": "traceability", "column": "", "row_index": i,
                    "description": f"第{i+1}行有数据但未标注来源",
                    "severity": "warning",
                })

    # Consistency: 多行提醒
    if len(rows) > 1:
        issues.append({
            "level": "consistency", "column": "", "row_index": -1,
            "description": "多行数据需确认跨行单位一致性",
            "severity": "warning",
        })

    return issues


def _to_float(val) -> float:
    """把提取值转成浮点数，转不了返回 None（"未检出"、">100" 等都属于转不了）。"""
    try:
        s = str(val).strip().replace(",", "")
        return float(s)
    except (TypeError, ValueError):
        return None


def _in_range(num: float, rng: str) -> bool:
    """判断数值是否落在 "min-max" 形式的区间内；区间写错则放行，不误报。"""
    try:
        low, high = [float(x.strip()) for x in str(rng).split("-", 1)]
        return low <= num <= high
    except (ValueError, TypeError):
        return True


def _llm_check(rows: List[dict], columns: List[dict], pdf_text: str) -> List[dict]:
    """使用 LLM 进行深度语义检查。"""
    col_names = [c["col_name"] for c in columns]

    prompt = f"""你是数据质量审计员。检查以下提取数据：

模板列：{col_names}
行数：{len(rows)}
数据：{json.dumps(rows, ensure_ascii=False)[:2000]}

执行四级检查（completeness/plausibility/consistency/traceability）。
返回JSON：{{"issues": [{{"level": "", "column": "", "row_index": 0,
"description": "", "severity": "error或warning"}}], "overall_pass": true/false}}"""

    system = "你是数据质量审计员。只返回JSON。"
    response = call_llm(prompt, system=system)
    try:
        result = json.loads(response)
        return result.get("issues", [])
    except Exception:
        return []


def _build_detail(issues: List[dict], passed: bool) -> str:
    """构建人类可读的验证报告。"""
    status = "PASS" if passed else "FAIL"
    error_count = sum(1 for i in issues if i.get("severity") == "error")
    warn_count = sum(1 for i in issues if i.get("severity") == "warning")
    lines = [f"[{status}] 验证{'通过' if passed else '未通过'} — "
             f"{error_count} 错误, {warn_count} 警告", ""]

    labels = {"completeness": "完整性", "plausibility": "合理性",
              "consistency": "一致性", "traceability": "可追溯性"}

    for issue in issues:
        lvl = labels.get(issue.get("level", ""), issue.get("level", ""))
        sev = issue.get("severity", "")
        desc = issue.get("description", "")
        lines.append(f"  [{sev.upper()}] [{lvl}] {desc}")

    return "\n".join(lines)
