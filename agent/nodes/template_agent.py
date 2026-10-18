"""Template Agent — 将用户需求（Excel 模板或自然语言描述）转化为列定义。

处理两种模式：
- Excel 模式：读取 .xlsx 表头 → LLM 分析每列的语义含义
- 自然语言模式：从领域知识生成合适的列定义
- Pass-through：如果 columns 已确认，跳过
"""

from agent.state import ExtractionState
from agent.tools.excel_reader import extract_headers, extract_sample_rows
from agent.tools.llm_utils import call_llm, parse_json_response
from prompts import load_prompt


def template_agent(state: ExtractionState) -> dict:
    """分析模板/需求 → 生成 List[ColumnDef]。

    如果 columns 已存在且 template_confirmed 为 True（批量处理中重复使用），
    直接返回空字典跳过。
    """
    # Pass-through：批量处理时模板只分析一次
    if state.get("template_confirmed") and state.get("columns"):
        return {}

    template_source = state.get("template_source", "")

    if template_source == "excel":
        columns = _analyze_from_excel(state)
    elif template_source == "natural_language":
        columns = _analyze_from_nl(state)
    else:
        return {"error": "未指定模板来源。请设置 template_source 为 'excel' 或 'natural_language'。"}

    return {"columns": columns}


def _analyze_from_excel(state: ExtractionState) -> list:
    """从 Excel 模板读取表头，LLM 只补充语义元数据，列名原样保留。"""
    excel_path = state["excel_path"]
    col_names = extract_headers(excel_path)
    sample_rows = extract_sample_rows(excel_path, n=3)

    # 用原始列名构建基础 ColumnDef，确保列名不变
    base_columns = {
        name: {
            "col_name": name,
            "semantic_type": "",
            "unit": "",
            "description": "",
            "expected_range": "",
        }
        for name in col_names
    }

    # 让 LLM 为每列补充语义信息（不修改列名）
    sample_str = str(sample_rows) if sample_rows else "（无样本数据）"
    prompt = (
        f"以下是 Excel 模板的列名列表和样本数据。请为每列补充语义信息。\n\n"
        f"## 列名（必须原样保留，不得改名、合并或删减）\n"
        f"{chr(10).join(col_names)}\n\n"
        f"## 样本数据\n{sample_str}\n\n"
        f"为每列返回 JSON，字段：col_name（必须与上述列名完全一致）、"
        f"semantic_type、unit、description、expected_range。\n"
        f"semantic_type 取值：substrate_property | condition | gas_production | metadata\n"
        f"只返回 JSON 数组，不要增减列，不要改名。"
    )

    system = (
        "你是一名文献数据提取模板的分析专家。"
        "列名必须原样保留，不得改名、合并或删减。只返回 JSON 数组。"
    )
    try:
        response = call_llm(prompt, system=system)
        llm_columns = parse_json_response(response)
        if isinstance(llm_columns, dict):
            llm_columns = [llm_columns]
    except Exception:
        llm_columns = []

    # 用 LLM 返回的元数据补充 base_columns（强制 col_name 不变）
    llm_map = {}
    for col in llm_columns:
        name = col.get("col_name", "")
        if name:
            llm_map[name] = col

    result = []
    for name, col in base_columns.items():
        if name in llm_map:
            enriched = llm_map[name]
            col["semantic_type"] = enriched.get("semantic_type", "")
            col["unit"] = enriched.get("unit", "")
            col["description"] = enriched.get("description", "")
            col["expected_range"] = enriched.get("expected_range", "")
        result.append(col)

    return result


def _analyze_from_nl(state: ExtractionState) -> list:
    """从自然语言描述生成列定义。"""
    nl_query = state.get("natural_language_query", "")

    if not nl_query.strip():
        return []

    template = load_prompt("template_agent")
    prompt = (
        f"请根据以下自然语言描述，生成合适的列定义：\n\n"
        f"用户需求：{nl_query}\n\n"
        f"请为该需求生成完整的列定义 JSON 数组。如果涉及厌氧发酵/沼气/AD 领域，"
        f"考虑常见参数如 TS、VS、pH、温度、沼气产量、甲烷含量等。"
    )

    system = "你是一名文献数据提取模板的分析专家。只返回 JSON 数组。"
    response = call_llm(prompt, system=system)
    columns = parse_json_response(response)

    if isinstance(columns, dict):
        columns = [columns]
    return columns
