"""Test agent/nodes/template_agent.py — 模板分析逻辑。"""

import json
from unittest.mock import patch

import pytest

from agent.nodes.template_agent import template_agent


# ═══ Mock 数据 ═══

MOCK_LLM_COLUMNS_RESPONSE = json.dumps([
    {"col_name": "铅含量", "semantic_type": "measured_value",
     "unit": "%", "description": "总固体含量", "expected_range": "0-100"},
    {"col_name": "镉含量", "semantic_type": "measured_value",
     "unit": "%", "description": "挥发性固体含量", "expected_range": "0-100"},
    {"col_name": "pH", "semantic_type": "measured_value",
     "unit": "", "description": "pH值", "expected_range": "0-14"},
])

MOCK_COLUMN_NAMES = ["铅含量", "镉含量", "pH"]


@pytest.fixture
def excel_state():
    """Excel 模式的初始 State。"""
    return {
        "excel_path": "data/sample_template.xlsx",
        "natural_language_query": "",
        "template_source": "excel",
        "columns": [],
        "template_confirmed": False,
    }


@pytest.fixture
def nl_state():
    """自然语言模式的初始 State。"""
    return {
        "excel_path": "",
        "natural_language_query": "提取水质检测报告中的TS、VS、pH数据",
        "template_source": "natural_language",
        "columns": [],
        "template_confirmed": False,
    }


class TestTemplateAgent:
    """Template Agent 核心功能测试。"""

    def test_pass_through_when_confirmed(self, excel_state):
        """模板已确认时应跳过分析，返回空字典。"""
        excel_state["template_confirmed"] = True
        excel_state["columns"] = [{"col_name": "铅含量", "semantic_type": "measured_value"}]

        result = template_agent(excel_state)
        assert result == {}

    def test_no_template_source(self):
        """未指定 template_source 时应返回错误。"""
        state = {
            "excel_path": "",
            "natural_language_query": "",
            "template_source": "",
            "columns": [],
            "template_confirmed": False,
        }
        result = template_agent(state)
        assert "error" in result
        assert "未指定模板来源" in result["error"]


class TestTemplateAgentExcelMode:
    """Excel 模式测试（mock LLM）。"""

    @patch("agent.nodes.template_agent.call_llm")
    @patch("agent.nodes.template_agent.extract_headers")
    @patch("agent.nodes.template_agent.extract_sample_rows")
    def test_excel_parse_columns(
        self, mock_sample_rows, mock_headers, mock_llm, excel_state
    ):
        """Excel 模式应正确解析 LLM 返回的 ColumnDef 列表。"""
        mock_headers.return_value = MOCK_COLUMN_NAMES
        mock_sample_rows.return_value = []
        mock_llm.return_value = MOCK_LLM_COLUMNS_RESPONSE

        result = template_agent(excel_state)
        assert "columns" in result
        assert len(result["columns"]) == 3
        assert result["columns"][0]["col_name"] == "铅含量"

    @patch("agent.nodes.template_agent.call_llm")
    @patch("agent.nodes.template_agent.extract_headers")
    @patch("agent.nodes.template_agent.extract_sample_rows")
    def test_excel_json_in_code_block(
        self, mock_sample_rows, mock_headers, mock_llm, excel_state
    ):
        """LLM 返回 JSON 包裹在 markdown 代码块中时应正确解析。"""
        mock_headers.return_value = MOCK_COLUMN_NAMES
        mock_sample_rows.return_value = []
        mock_llm.return_value = f"```json\n{MOCK_LLM_COLUMNS_RESPONSE}\n```"

        result = template_agent(excel_state)
        assert len(result["columns"]) == 3


    @patch("agent.nodes.template_agent.call_llm")
    @patch("agent.nodes.template_agent.extract_headers")
    @patch("agent.nodes.template_agent.extract_sample_rows")
    def test_preserves_all_original_columns(
        self, mock_sample_rows, mock_headers, mock_llm, excel_state
    ):
        """LLM 只返回部分列时，结果仍包含所有原始列。"""
        mock_headers.return_value = MOCK_COLUMN_NAMES
        mock_sample_rows.return_value = []
        mock_llm.return_value = json.dumps([
            {"col_name": "铅含量", "semantic_type": "measured_value",
             "unit": "%", "description": "总固体"},
            {"col_name": "镉含量", "semantic_type": "measured_value",
             "unit": "%", "description": "挥发性固体"},
        ])

        result = template_agent(excel_state)
        assert len(result["columns"]) == 3
        col_names = [c["col_name"] for c in result["columns"]]
        assert col_names == ["铅含量", "镉含量", "pH"]
        ph_col = [c for c in result["columns"] if c["col_name"] == "pH"][0]
        assert ph_col["semantic_type"] == ""

    @patch("agent.nodes.template_agent.call_llm")
    @patch("agent.nodes.template_agent.extract_headers")
    @patch("agent.nodes.template_agent.extract_sample_rows")
    def test_llm_rename_is_ignored(
        self, mock_sample_rows, mock_headers, mock_llm, excel_state
    ):
        """LLM 改了列名时强制使用原始列名。"""
        mock_headers.return_value = ["铅含量", "pH"]
        mock_sample_rows.return_value = []
        mock_llm.return_value = json.dumps([
            {"col_name": "Total_Solids", "semantic_type": "measured_value",
             "unit": "%", "description": "total"},
            {"col_name": "pH", "semantic_type": "measured_value",
             "unit": "", "description": "pH"},
        ])

        result = template_agent(excel_state)
        col_names = [c["col_name"] for c in result["columns"]]
        assert col_names == ["铅含量", "pH"]
        ts_col = [c for c in result["columns"] if c["col_name"] == "铅含量"][0]
        assert ts_col["semantic_type"] == ""


class TestTemplateAgentNLMode:
    """自然语言模式测试（mock LLM）。"""

    @patch("agent.nodes.template_agent.call_llm")
    def test_nl_parse_columns(self, mock_llm, nl_state):
        """自然语言模式应正确解析 LLM 返回的列定义。"""
        mock_llm.return_value = MOCK_LLM_COLUMNS_RESPONSE

        result = template_agent(nl_state)
        assert "columns" in result
        assert len(result["columns"]) == 3

    @patch("agent.nodes.template_agent.call_llm")
    def test_nl_empty_query(self, mock_llm, nl_state):
        """空查询应返回空列列表。"""
        nl_state["natural_language_query"] = ""

        result = template_agent(nl_state)
        assert result["columns"] == []

    @patch("agent.nodes.template_agent.call_llm")
    def test_nl_single_column_dict_response(self, mock_llm, nl_state):
        """LLM 返回单个 dict（而非列表）时应自动包装为列表。"""
        single_col = json.dumps({
            "col_name": "pH", "semantic_type": "measured_value",
            "unit": "", "description": "pH值", "expected_range": "0-14",
        })
        mock_llm.return_value = single_col

        result = template_agent(nl_state)
        assert len(result["columns"]) == 1
        assert result["columns"][0]["col_name"] == "pH"
