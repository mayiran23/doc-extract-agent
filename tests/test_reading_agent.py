"""Test agent/nodes/reading_agent.py — PDF 文本提取逻辑。"""

from unittest.mock import patch

import pytest

from agent.nodes.reading_agent import reading_agent


@pytest.fixture
def state_with_pdf():
    """含 current_pdf 的 State。"""
    return {"current_pdf": "/fake/path/test_paper.pdf"}


class TestReadingAgent:
    """Reading Agent 核心功能测试。"""

    def test_no_pdf_path(self):
        """未指定 PDF 路径时应返回错误。"""
        result = reading_agent({"current_pdf": ""})
        assert "error" in result

    @patch("agent.nodes.reading_agent.is_scanned_pdf")
    def test_scanned_pdf_detection(self, mock_scanned, state_with_pdf):
        """扫描版 PDF 应设置 error 字段。"""
        mock_scanned.return_value = True

        result = reading_agent(state_with_pdf)
        assert "error" in result
        assert "扫描版" in result["error"]
        assert result["pdf_text"] == ""

    @patch("agent.nodes.reading_agent.extract_text")
    @patch("agent.nodes.reading_agent.is_scanned_pdf")
    def test_text_extraction(self, mock_scanned, mock_extract, state_with_pdf):
        """正常 PDF 应返回提取文本和 paper_id。"""
        mock_scanned.return_value = False
        mock_extract.return_value = "--- Page 1 ---\nTest content"

        result = reading_agent(state_with_pdf)
        assert result["pdf_text"] == "--- Page 1 ---\nTest content"
        assert result["current_paper_id"] == "test_paper"

    @patch("agent.nodes.reading_agent.extract_text")
    @patch("agent.nodes.reading_agent.is_scanned_pdf")
    def test_paper_id_from_filename(self, mock_scanned, mock_extract):
        """paper_id 应从文件名正确派生。"""
        mock_scanned.return_value = False
        mock_extract.return_value = "content"

        result = reading_agent({"current_pdf": "/path/to/cattle_manure_digestion.pdf"})
        assert result["current_paper_id"] == "cattle_manure_digestion"

    @patch("agent.nodes.reading_agent.extract_text")
    @patch("agent.nodes.reading_agent.is_scanned_pdf")
    def test_file_not_found(self, mock_scanned, mock_extract, state_with_pdf):
        """文件不存在时应返回 error。"""
        mock_scanned.return_value = False
        mock_extract.side_effect = FileNotFoundError("No such file")

        result = reading_agent(state_with_pdf)
        assert "error" in result

    @patch("agent.nodes.reading_agent.extract_text")
    @patch("agent.nodes.reading_agent.is_scanned_pdf")
    def test_full_text_preserved(self, mock_scanned, mock_extract, state_with_pdf):
        """全文应完整保留（不再硬截断）。"""
        mock_scanned.return_value = False
        long_text = "X" * 50000
        mock_extract.return_value = long_text

        result = reading_agent(state_with_pdf)
        assert len(result["pdf_text"]) == 50000
