"""LangGraph Agent 的共享状态定义。

所有 Node 都读写这个 State。关键设计：
- all_rows 使用 Annotated reducer 实现累加而非覆盖
- current_rows 是 Reflection 循环的工作区，通过后才合并到 all_rows
- extraction_hints 在每份报告开始时清空，Reflection 不通过时填充
"""

import operator
from typing import Annotated, Dict, List, Literal, Optional

from typing import TypedDict


class ColumnDef(TypedDict, total=False):
    """模板中一列的定义，由 Template Agent 生成。"""

    col_name: str  # 原始列名（如 "检测值"、"标准限值"）
    semantic_type: str  # 语义类别：sample_id | test_item | measured_value | limit_value | judgment | metadata
    unit: str  # 期望单位（如 "%"、"°C"、"ml/kg"）
    description: str  # LLM 生成的列含义说明
    expected_range: str  # 合理性范围（如 "0-100"、"0-14"），用于 Validation


class DataRow(TypedDict, total=False):
    """一行提取数据，对应一份报告中的一个检测项目。"""

    paper_id: str  # 文档标识（从文件名派生）
    sequence_id: str  # 检测项序号（S1-01, S1-02, ...）
    values: Dict[str, str]  # {列名: 提取值}，未报告则空字符串
    source_table: str  # 数据来源表（如 "检测结果表"）
    source_figure: str  # 数据来源位置（如 "第2页"）
    notes: str  # 备注：从图读取标注、单位转换说明等


class ValidationIssue(TypedDict):
    """Validation Engine 发现的一个问题。"""

    level: Literal["completeness", "plausibility", "consistency", "traceability"]
    column: str  # 涉及列名（行级问题时为空）
    row_index: int  # current_rows 中的行索引
    description: str  # 人类可读的问题描述
    severity: Literal["error", "warning"]


class ExtractionState(TypedDict, total=False):
    """全局共享状态 — LangGraph 中所有 Node 的输入和输出。

    按功能分组：
    - 输入配置：excel_path, natural_language_query, template_source
    - 模板分析：columns, template_confirmed
    - 当前报告上下文：current_pdf, current_paper_id, pdf_text, citation
    - 提取结果：current_rows（工作区）, all_rows（累加器）
    - 验证：validation_passed, validation_issues, validation_detail
    - Reflection：extraction_hints, reflection_rounds
    - 控制：error, paper_completed, notification
    """

    # ── 输入配置 ──
    excel_path: str  # Excel 模板路径（模式 A）
    natural_language_query: str  # 自然语言需求描述（模式 B）
    template_source: str  # "excel" 或 "natural_language"

    # ── 模板分析（Template Agent 设置一次）──
    columns: List[ColumnDef]  # 解析/确认后的列定义
    template_confirmed: bool  # 用户是否已在 UI 确认列定义

    # ── 当前报告上下文 ──
    current_pdf: str  # 当前 PDF 的绝对路径
    current_paper_id: str  # 从文件名派生的短标识
    pdf_text: str  # 带页码标记的完整提取文本
    citation: str  # 报告元信息摘要（报告编号/机构/样品/日期/依据标准）

    # ── 提取结果 ──
    # 当前报告的工作行 — Reflection 循环时可能被替换
    current_rows: List[DataRow]
    # 已通过验证的行 — Annotated reducer 确保累加而非覆盖
    all_rows: Annotated[List[DataRow], operator.add]

    # ── 验证结果 ──
    validation_passed: bool  # 四级检查是否全部通过
    validation_issues: List[ValidationIssue]  # 结构化问题列表
    validation_detail: str  # 完整验证报告文本（供 UI 展示）

    # ── Reflection / 重试 ──
    extraction_hints: str  # Reflection 生成的修正指引，注入 Extraction 的下一次调用
    reflection_rounds: int  # 当前报告的重试计数器

    # ── 控制 ──
    error: Optional[str]  # 致命错误信息（非空时跳过当前报告）
    paper_completed: bool  # 当前报告是否处理完毕
    notification: str  # 人类可读的状态更新消息（供 UI 展示）
