"""Test agent/nodes/citation_agent.py — 引文提取和格式化逻辑。"""

import json
from unittest.mock import patch

import pytest

from agent.nodes.citation_agent import (
    _extract_metadata,
    _format_citation,
    citation_agent,
)

MOCK_METADATA = json.dumps({
    "title": "Anaerobic Co-digestion of Cattle Manure and Corn Straw",
    "first_author": "Zhang, S.",
    "authors": "Zhang, S., Li, W., Wang, X.",
    "journal": "Bioresource Technology",
    "year": "2024",
    "volume": "350",
    "issue": "",
    "pages": "126-135",
    "doi": "",
    "type": "J",
})


class TestCitationAgent:
    """Citation Agent 核心功能测试。"""

    def test_empty_pdf_text(self):
        """空文本应返回空引文。"""
        result = citation_agent({"pdf_text": ""})
        assert result["citation"] == ""

    @patch("agent.nodes.citation_agent.call_llm")
    def test_extract_metadata(self, mock_llm):
        """应正确解析 LLM 返回的元数据 JSON。"""
        mock_llm.return_value = MOCK_METADATA

        metadata = _extract_metadata("Sample paper text...")
        assert metadata["title"] == "Anaerobic Co-digestion of Cattle Manure and Corn Straw"
        assert metadata["year"] == "2024"
        assert metadata["type"] == "J"

    @patch("agent.nodes.citation_agent.call_llm")
    def test_full_flow_returns_citation(self, mock_llm):
        """完整流程应返回格式化的引文字符串。"""
        mock_llm.return_value = MOCK_METADATA

        result = citation_agent({"pdf_text": "Sample paper text..." * 100})
        assert result["citation"]
        assert "Zhang" in result["citation"]
        assert "2024" in result["citation"]

    @patch("agent.nodes.citation_agent.call_llm")
    def test_llm_error_is_handled(self, mock_llm):
        """LLM 返回无效 JSON 时应优雅降级。"""
        mock_llm.return_value = "not valid json"

        result = citation_agent({"pdf_text": "Sample text"})
        assert result["citation"] == ""


class TestFormatCitation:
    """引文格式化测试。"""

    def test_full_citation(self):
        """完整元数据应生成正确格式的引文。"""
        meta = {
            "authors": "Zhang, S., Li, W.",
            "title": "Test Paper Title",
            "type": "J",
            "journal": "Bioresource Technology",
            "year": "2024",
            "volume": "350",
            "issue": "",
            "pages": "126-135",
            "doi": "10.1234/test",
        }
        citation = _format_citation(meta)
        assert "Zhang, S., Li, W." in citation
        assert "Test Paper Title" in citation
        assert "[J]" in citation
        assert "Bioresource Technology" in citation
        assert "2024" in citation
        assert "DOI: 10.1234/test" in citation

    def test_minimal_citation(self):
        """仅有标题和作者时的最小引文。"""
        meta = {
            "authors": "Smith, J.",
            "title": "A Study",
            "type": "J",
            "journal": "",
            "year": "",
            "volume": "",
            "issue": "",
            "pages": "",
            "doi": "",
        }
        citation = _format_citation(meta)
        assert "Smith, J." in citation
        assert "A Study[J]" in citation

    def test_empty_metadata(self):
        """空元数据应返回空字符串。"""
        assert _format_citation({}) == ""

    def test_no_title(self):
        """无标题的元数据应返回空字符串。"""
        assert _format_citation({"title": ""}) == ""

    def test_degree_thesis_type(self):
        """学位论文应使用 [D] 标记。"""
        meta = {
            "authors": "王明",
            "title": "厌氧发酵研究",
            "type": "D",
            "journal": "清华大学",
            "year": "2023",
            "volume": "",
            "issue": "",
            "pages": "",
            "doi": "",
        }
        citation = _format_citation(meta)
        assert "[D]" in citation
        assert "清华大学" in citation
