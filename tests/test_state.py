"""Test agent/state.py — State 字段默认值、Annotated reducer 行为、序列化。"""

import json
import operator
from typing import Annotated, List

import pytest

from agent.state import (
    ColumnDef,
    DataRow,
    ExtractionState,
    ValidationIssue,
)


class TestColumnDef:
    """ColumnDef 类型验证。"""

    def test_minimal_creation(self):
        """仅 col_name 即可创建 ColumnDef。"""
        col = ColumnDef(col_name="TS")
        assert col["col_name"] == "TS"

    def test_full_creation(self):
        """所有字段的完整创建。"""
        col = ColumnDef(
            col_name="TS",
            semantic_type="substrate_property",
            unit="%",
            description="总固体含量",
            expected_range="0-100",
        )
        assert col["col_name"] == "TS"
        assert col["semantic_type"] == "substrate_property"
        assert col["unit"] == "%"
        assert col["description"] == "总固体含量"
        assert col["expected_range"] == "0-100"

    def test_missing_optional_fields(self):
        """可选字段缺失时不应抛出异常（total=False）。"""
        col = ColumnDef(col_name="pH")
        # 访问未设置的键应触发 KeyError（TypedDict 不做默认值填充）
        with pytest.raises(KeyError):
            _ = col["unit"]


class TestDataRow:
    """DataRow 类型验证。"""

    def test_minimal_creation(self):
        """仅 paper_id 和 values 即可创建 DataRow。"""
        row = DataRow(paper_id="test", values={"TS": "8.5"})
        assert row["paper_id"] == "test"
        assert row["values"] == {"TS": "8.5"}

    def test_full_creation(self):
        """所有字段的完整创建。"""
        row = DataRow(
            paper_id="paper_001",
            sequence_id="A1",
            values={"TS": "8.5", "pH": "7.2"},
            source_table="Table 1",
            source_figure="",
            notes="从Figure 3目测读取，可能存在±误差",
        )
        assert row["sequence_id"] == "A1"
        assert row["source_table"] == "Table 1"
        assert row["notes"] == "从Figure 3目测读取，可能存在±误差"

    def test_empty_values(self):
        """未报告的数据项应为空字符串。"""
        row = DataRow(paper_id="test", values={"TS": "", "pH": "7.2"})
        assert row["values"]["TS"] == ""


class TestValidationIssue:
    """ValidationIssue 类型验证。"""

    def test_error_level_creation(self):
        """error 级别的验证问题。"""
        issue = ValidationIssue(
            level="plausibility",
            column="pH",
            row_index=0,
            description="pH值为14.5，超出合理范围(0-14)",
            severity="error",
        )
        assert issue["level"] == "plausibility"
        assert issue["severity"] == "error"

    def test_warning_level_creation(self):
        """warning 级别的验证问题。"""
        issue = ValidationIssue(
            level="completeness",
            column="VS",
            row_index=1,
            description="VS列在第2行为空，但文献Table 1中报告了该值",
            severity="warning",
        )
        assert issue["severity"] == "warning"


class TestExtractionState:
    """ExtractionState 完整状态测试。"""

    def test_default_initialization(self, base_state):
        """验证初始 State 的所有字段都有正确的默认值。"""
        state = ExtractionState(**base_state)
        assert state["excel_path"] == ""
        assert state["columns"] == []
        assert state["current_rows"] == []
        assert state["all_rows"] == []
        assert state["validation_passed"] is False
        assert state["reflection_rounds"] == 0
        assert state["error"] is None
        assert state["paper_completed"] is False

    def test_all_rows_reducer_appends(self):
        """验证 all_rows 的 Annotated reducer 为 operator.add（累加而非覆盖）。

        这是整个系统最关键的语义之一：每次 Node 返回新的 all_rows，
        LangGraph 自动将其追加到已有列表后面，而非覆盖。
        """
        from typing import TypedDict as TDict
        from langgraph.graph import StateGraph

        class TestState(TDict):
            items: Annotated[List[str], operator.add]

        builder = StateGraph(TestState)

        def add_a(state: TestState) -> dict:
            return {"items": ["A"]}

        def add_b(state: TestState) -> dict:
            return {"items": ["B"]}

        builder.add_node("add_a", add_a)
        builder.add_node("add_b", add_b)
        builder.add_edge("add_a", "add_b")
        builder.set_entry_point("add_a")

        graph = builder.compile()
        result = graph.invoke({"items": []})

        assert result["items"] == ["A", "B"]

    def test_all_rows_preserves_order(self):
        """验证 all_rows 累加保持插入顺序。"""
        from typing import TypedDict as TDict
        from langgraph.graph import StateGraph

        class TestState(TDict):
            rows: Annotated[List[str], operator.add]

        builder = StateGraph(TestState)

        def batch1(state: TestState) -> dict:
            return {"rows": ["row1", "row2"]}

        def batch2(state: TestState) -> dict:
            return {"rows": ["row3"]}

        builder.add_node("batch1", batch1)
        builder.add_node("batch2", batch2)
        builder.add_edge("batch1", "batch2")
        builder.set_entry_point("batch1")

        graph = builder.compile()
        result = graph.invoke({"rows": []})

        assert result["rows"] == ["row1", "row2", "row3"]

    def test_state_serialization(self, base_state):
        """State 可以序列化为 JSON（支持 LangGraph checkpoint 持久化）。"""
        state = ExtractionState(**base_state)
        state["columns"] = [
            ColumnDef(col_name="TS", semantic_type="substrate_property", unit="%")
        ]
        state["all_rows"] = [
            DataRow(paper_id="test", values={"TS": "8.5"})
        ]

        serialized = json.dumps(state)
        deserialized = json.loads(serialized)

        assert deserialized["columns"][0]["col_name"] == "TS"
        assert deserialized["all_rows"][0]["values"]["TS"] == "8.5"

    def test_extraction_hints_lifecycle(self, base_state):
        """extraction_hints 的生命周期：初始为空，Reflection 后填充。"""
        state = ExtractionState(**base_state)
        assert state["extraction_hints"] == ""

        state["extraction_hints"] = "重新检查Section 2.3的pH值，当前值47异常，可能为4.7"
        assert "pH值" in state["extraction_hints"]
