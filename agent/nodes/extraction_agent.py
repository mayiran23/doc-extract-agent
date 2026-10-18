"""Extraction Agent — 分块全量提取 + 报告结构分析。

策略（不依赖正则定位，由 LLM 自主判断数据所在）：
1. 报告结构分析：让 LLM 先理解报告的版式布局和检测项目分布
2. 简单字符分块：每 ~10K 字符一块，不做智能筛选
3. 逐块提取：每块独立调用 LLM 提取检测项数据
4. 合并去重：汇总所有块的结果，基于样品号 + 检测项目去重
"""

from typing import List

from agent.state import ExtractionState
from agent.tools.llm_utils import call_llm, parse_json_response
from config.settings import settings


def extraction_agent(state: ExtractionState) -> dict:
    """分块全量提取：全文分块 → 每块 LLM 提取 → 合并去重。"""
    pdf_text = state.get("pdf_text", "")
    columns = state.get("columns", [])
    hints = state.get("extraction_hints", "")

    if not pdf_text or not columns:
        return {"current_rows": []}

    col_desc = _build_column_description(columns)
    chunk_size = settings.pdf_chunk_size
    max_chunks = settings.pdf_max_chunks

    # ── Step 0: 报告结构分析（可选，短文本跳过）──
    structure_hint = ""
    if len(pdf_text) > chunk_size:
        try:
            structure_hint = _analyze_structure(pdf_text[:8000], columns)
        except Exception:
            pass

    # ── Step 1: 分块 ──
    chunks = _chunk_text(pdf_text, chunk_size, max_chunks)

    # ── Step 2: 逐块提取 ──
    all_rows = []
    for i, chunk in enumerate(chunks):
        chunk_label = f"第{i+1}/{len(chunks)}块"
        try:
            prompt = _build_chunk_prompt(
                col_desc, chunk, chunk_label, structure_hint, hints
            )
            system = (
                "你是一名检测报告数据提取专家。只返回 JSON 数组。"
                "严格遵循提取规则，不编造数据。"
            )
            response = call_llm(prompt, system=system)
            chunk_rows = parse_json_response(response)

            if isinstance(chunk_rows, dict):
                chunk_rows = [chunk_rows]
            if isinstance(chunk_rows, list):
                all_rows.extend(chunk_rows)
        except Exception:
            continue

    # ── Step 3: 合并去重 ──
    merged = _merge_and_deduplicate(all_rows, columns, hints)

    paper_id = state.get("current_paper_id", "unknown")
    merged = _post_process(merged, paper_id, columns)

    return {"current_rows": merged}


def _chunk_text(text: str, chunk_size: int, max_chunks: int) -> List[str]:
    """将文本按指定大小均匀分块，保持页边界完整。

    每块尽量在 `--- Page N ---` 标记处断开，避免切断段落。
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text) and len(chunks) < max_chunks:
        end = min(start + chunk_size, len(text))

        # 在页面标记处断开
        if end < len(text):
            # 从 end 往前找最近的 "--- Page" 标记
            search_start = max(start, end - 500)
            page_marker = text.rfind("\n--- Page ", search_start, end)
            if page_marker != -1:
                end = page_marker

        chunks.append(text[start:end])
        start = end

    return chunks


def _analyze_structure(text_head: str, columns: List[dict]) -> str:
    """让 LLM 先建立文档的整体结构认知，再逐块提取。

    报告类文档的字段分散在「样品信息」「检测结果表」「结论」几个区域，
    先让模型看清整体布局，比直接切块抽取的命中率高。
    """
    col_names = [c["col_name"] for c in columns]
    prompt = (
        "你是一名检测报告结构分析师。请先阅读以下报告文本的开头部分，"
        "然后回答三个问题：\n\n"
        f"报告文本：\n{text_head}\n\n"
        "请简要回答：\n"
        "1. 这份报告包含哪些样品或检测批次？（列出样品编号）\n"
        "2. 检测项目和数值所在的表格出现在文本的什么位置？\n"
        f"3. 这些数据对应模板中的哪些列？模板列：{col_names}\n\n"
        "用中文简要回答，不超过300字。"
    )
    response = call_llm(prompt)
    return response.strip()


def _build_chunk_prompt(
    col_desc: str,
    chunk_text: str,
    chunk_label: str,
    structure_hint: str,
    hints: str,
) -> str:
    """构建单个分块的提取 prompt。"""
    parts = [
        f"你正在提取检测报告数据（{chunk_label}）。请从以下文本片段中提取检测项数据。\n",
    ]

    if structure_hint:
        parts.extend([
            "## 报告结构分析（供参考）\n",
            structure_hint,
            "\n",
        ])

    parts.extend([
        "## 模板列定义（只填报告中明确写出的值，未写出则留空）\n",
        col_desc,
        "\n## 当前文本片段\n",
        chunk_text,
        "\n## 提取规则\n",
        _extraction_rules(),
    ])

    if hints:
        parts.extend([
            "\n## 上一轮的修正指引\n",
            hints,
        ])

    parts.extend([
        "\n## 输出格式\n",
        'JSON数组：[{"sequence_id": "S1-01", "values": {"列名": "值"}, '
        '"source_table": "检测结果表", "source_figure": "第2页", '
        '"notes": "备注说明"}]',
        "\n只返回 JSON 数组。如果没有可提取的数据，返回 []。",
    ])

    return "\n".join(parts)


def _merge_and_deduplicate(
    rows: List[dict], columns: List[dict], hints: str
) -> List[dict]:
    """合并多个分块的提取结果，去重。

    策略：如果多块返回了相同的实验组（相同 sequence_id），
    保留 values 更丰富的那一行。
    """
    if not rows:
        return []

    col_names = [c["col_name"] for c in columns]
    merged = {}
    # 同时尝试用 sequence_id 匹配
    for row in rows:
        seq = row.get("sequence_id", "")
        values = row.get("values", {})

        if not seq:
            # 没有序号的行，直接保留
            continue

        if seq not in merged:
            merged[seq] = row
        else:
            # 合并：新行有更多非空值则替换旧值
            existing_values = merged[seq].get("values", {})
            for cn in col_names:
                if values.get(cn) and not existing_values.get(cn):
                    existing_values[cn] = values.get(cn)
            merged[seq]["values"] = existing_values
            # 保留更详细的来源信息
            if row.get("source_table") and not merged[seq].get("source_table"):
                merged[seq]["source_table"] = row["source_table"]
            if row.get("source_figure") and not merged[seq].get("source_figure"):
                merged[seq]["source_figure"] = row["source_figure"]

    # 没有 sequence_id 的行追加到后面
    result = list(merged.values())
    for row in rows:
        if not row.get("sequence_id"):
            result.append(row)

    return result


def _build_column_description(columns: List[dict]) -> str:
    """构建列定义的文本描述。"""
    parts = []
    for c in columns:
        unit = c.get("unit", "未指定") or "未指定"
        desc = c.get("description", c["col_name"])
        parts.append(
            f"- {c['col_name']}（单位：{unit}）：{desc}"
        )
    return "\n".join(parts)


def _extraction_rules() -> str:
    """提取规则。"""
    return """1. 不编造数据：只填报告中明确写出的值，未写出则留空。
2. 分项分行：每个检测项目作为独立行，同一份报告内用 S1-01, S1-02 编号。
3. 来源追溯：source_table 填表格名称（如"检测结果表"），source_figure 填页码（如"第2页"）。
4. 判定结论只抄不算：只记录报告原文的结论（合格/不合格/符合/不符合），不要根据限值自行推断。
5. 单位：使用模板列定义中的单位，如需换算在 notes 中说明原始值与换算过程。"""


def _post_process(
    rows: List[dict], paper_id: str, columns: List[dict]
) -> List[dict]:
    """后处理：注入 paper_id、补齐序号、去重。"""
    col_names = [c["col_name"] for c in columns]
    processed = []
    exp_prefixes = {}
    exp_counter = ord("A")

    for row in rows:
        row["paper_id"] = paper_id

        if "values" not in row:
            row["values"] = {}
        for cn in col_names:
            row["values"].setdefault(cn, "")

        row.setdefault("source_table", "")
        row.setdefault("source_figure", "")

        source_key = (
            row.get("source_table", "")
            or row.get("source_figure", "")
            or row.get("sequence_id", "")
            or chr(exp_counter)
        )
        if source_key not in exp_prefixes:
            exp_prefixes[source_key] = chr(exp_counter)
            exp_counter += 1

        prefix = exp_prefixes.get(source_key, "A")

        if not row.get("sequence_id"):
            count = sum(
                1 for r in processed
                if (r.get("sequence_id") or "").startswith(prefix)
            )
            row["sequence_id"] = f"{prefix}{count + 1}"

        processed.append(row)

    return processed
