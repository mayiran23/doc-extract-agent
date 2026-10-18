"""Test agent/nodes/extraction_agent.py — 分块提取逻辑。"""

import json
from unittest.mock import patch

import pytest

from agent.nodes.extraction_agent import (
    _chunk_text,
    _merge_and_deduplicate,
    _post_process,
    extraction_agent,
)

MOCK_ROWS_RESPONSE = json.dumps([
    {
        "sequence_id": "A1",
        "values": {"铅含量": "8.5", "镉含量": "82.3", "pH": "7.2", "温度(°C)": "37"},
        "source_table": "Table 1",
        "source_figure": "",
        "notes": "",
    },
    {
        "sequence_id": "A2",
        "values": {"铅含量": "8.5", "镉含量": "82.3", "pH": "7.2", "温度(°C)": "37"},
        "source_table": "Table 2",
        "source_figure": "",
        "notes": "T2 treatment",
    },
])

SAMPLE_COLS = [
    {"col_name": "铅含量", "semantic_type": "measured_value", "unit": "%"},
    {"col_name": "镉含量", "semantic_type": "measured_value", "unit": "%"},
    {"col_name": "pH", "semantic_type": "measured_value", "unit": ""},
    {"col_name": "温度(°C)", "semantic_type": "measured_value", "unit": "°C"},
]


@pytest.fixture
def extraction_state():
    return {
        "current_pdf": "/path/test.pdf",
        "current_paper_id": "test_paper",
        "pdf_text": "Short text with TS=8.5, VS=82.3" * 20,  # ~600 chars
        "columns": SAMPLE_COLS,
        "extraction_hints": "",
        "reflection_rounds": 0,
    }


class TestExtractionAgent:
    """Extraction Agent 核心功能测试。"""

    def test_empty_text_returns_empty(self):
        """空文本应返回空行列表。"""
        result = extraction_agent({"pdf_text": "", "columns": []})
        assert result["current_rows"] == []

    def test_no_columns_returns_empty(self):
        """无列定义时应返回空行列表。"""
        result = extraction_agent({"pdf_text": "text", "columns": []})
        assert result["current_rows"] == []

    @patch("agent.nodes.extraction_agent.call_llm")
    def test_basic_extraction(self, mock_llm, extraction_state):
        """短文本单块提取：mock LLM 返回有效行。"""
        mock_llm.return_value = MOCK_ROWS_RESPONSE
        result = extraction_agent(extraction_state)
        assert len(result["current_rows"]) == 2
        assert result["current_rows"][0]["paper_id"] == "test_paper"

    @patch("agent.nodes.extraction_agent.call_llm")
    def test_llm_error_returns_empty(self, mock_llm, extraction_state):
        """LLM 调用失败时应返回空列表。"""
        mock_llm.side_effect = Exception("API error")
        result = extraction_agent(extraction_state)
        assert result["current_rows"] == []


class TestChunkText:
    """分块逻辑测试。"""

    def test_short_text_single_chunk(self):
        """短文本应返回单块。"""
        chunks = _chunk_text("Hello", 10000, 10)
        assert len(chunks) == 1

    def test_long_text_multiple_chunks(self):
        """长文本应分多块。"""
        text = "X" * 25000
        chunks = _chunk_text(text, 10000, 10)
        assert len(chunks) >= 2

    def test_max_chunks_limit(self):
        """分块数不超过上限。"""
        text = "X" * 100000
        chunks = _chunk_text(text, 5000, 3)
        assert len(chunks) == 3

    def test_page_boundary_split(self):
        """应在页面标记处断开。"""
        prefix = "A" * 5000
        suffix = (f"\n--- Page 2 ---\n" + "B" * 4000)
        text = prefix + suffix
        chunks = _chunk_text(text, 8000, 10)
        assert len(chunks) >= 1


class TestMergeAndDeduplicate:
    """合并去重测试。"""

    def test_different_sequences_kept(self):
        """不同 sequence_id 的行应全部保留。"""
        rows = [
            {"sequence_id": "A1", "values": {"铅含量": "8.5"}},
            {"sequence_id": "B1", "values": {"pH": "7.2"}},
        ]
        merged = _merge_and_deduplicate(rows, SAMPLE_COLS, "")
        assert len(merged) == 2

    def test_same_sequence_merged(self):
        """相同 sequence_id 的行应合并值。"""
        rows = [
            {"sequence_id": "A1", "values": {"铅含量": "8.5", "pH": ""}},
            {"sequence_id": "A1", "values": {"铅含量": "", "pH": "7.2"}},
        ]
        merged = _merge_and_deduplicate(rows, SAMPLE_COLS, "")
        assert len(merged) == 1
        assert merged[0]["values"]["铅含量"] == "8.5"
        assert merged[0]["values"]["pH"] == "7.2"


class TestPostProcess:
    """后处理逻辑测试。"""

    def test_paper_id_injection(self):
        rows = [{"values": {"铅含量": "8.5"}}]
        result = _post_process(rows, "paper_001", SAMPLE_COLS)
        assert result[0]["paper_id"] == "paper_001"

    def test_missing_columns_filled(self):
        rows = [{"values": {"铅含量": "8.5"}}]
        result = _post_process(rows, "test", SAMPLE_COLS)
        assert result[0]["values"].get("pH") == ""

    def test_sequence_numbering(self):
        rows = [
            {"values": {"铅含量": "8.5"}, "source_table": "Table 1"},
            {"values": {"镉含量": "82.3"}, "source_table": "Table 1"},
            {"values": {"pH": "7.2"}, "source_table": "Table 2"},
        ]
        result = _post_process(rows, "test", SAMPLE_COLS)
        assert result[0]["sequence_id"] == "A1"
        assert result[1]["sequence_id"] == "A2"
        assert result[2]["sequence_id"] == "B1"

    def test_no_figure_reading_annotation(self):
        """检测报告的数据是印在纸上的，不应自动补「目测读取」标注。"""
        rows = [{"values": {"铅含量": "85"}, "source_figure": "第1页", "notes": ""}]
        result = _post_process(rows, "test", SAMPLE_COLS)
        assert "目测" not in result[0]["notes"]

    def test_no_fabrication(self):
        rows = [{"values": {"铅含量": "8.5"}}]
        result = _post_process(rows, "test", SAMPLE_COLS)
        assert result[0]["values"]["镉含量"] == ""
