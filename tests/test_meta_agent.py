"""Test agent/nodes/meta_agent.py — 报告元信息提取与摘要格式化。"""

import json
from unittest.mock import patch

import pytest

from agent.nodes.meta_agent import (
    _extract_metadata,
    _format_summary,
    meta_agent,
)

MOCK_METADATA = json.dumps({
    "report_no": "JC2026-0431",
    "institution": "某某检测技术有限公司",
    "sample_id": "YP-2026-0087",
    "sample_name": "生活饮用水",
    "test_date": "2026-03-12",
    "standard_basis": "GB/T 5750-2023",
    "conclusion": "合格",
})


class TestMetaAgent:
    """Meta Agent 核心功能测试。"""

    def test_empty_pdf_text(self):
        """空文本应返回空摘要。"""
        result = meta_agent({"pdf_text": ""})
        assert result["citation"] == ""

    @patch("agent.nodes.meta_agent.call_llm")
    def test_extract_metadata(self, mock_llm):
        """应正确解析 LLM 返回的元信息 JSON。"""
        mock_llm.return_value = MOCK_METADATA
        result = _extract_metadata("dummy report text")
        assert result["report_no"] == "JC2026-0431"
        assert result["sample_name"] == "生活饮用水"

    @patch("agent.nodes.meta_agent.call_llm")
    def test_extract_metadata_bad_json(self, mock_llm):
        """LLM 返回非 JSON 时应降级为空字典，不抛异常。"""
        mock_llm.return_value = "抱歉，我无法提取"
        assert _extract_metadata("text") == {}

    def test_format_summary_contains_fields(self):
        """摘要应包含全部非空字段。"""
        summary = _format_summary(json.loads(MOCK_METADATA))
        assert "报告编号: JC2026-0431" in summary
        assert "检测机构: 某某检测技术有限公司" in summary
        assert "依据标准: GB/T 5750-2023" in summary

    def test_format_summary_skips_empty(self):
        """空字段不应出现在摘要里。"""
        summary = _format_summary({"report_no": "JC2026-0431", "institution": ""})
        assert "报告编号: JC2026-0431" in summary
        assert "检测机构" not in summary

    def test_format_summary_empty_dict(self):
        assert _format_summary({}) == ""

    def test_invalid_report_no_flagged(self):
        """编号不符合规范时应标记待核对。"""
        summary = _format_summary({"report_no": "abc"})
        assert "待核对" in summary

    def test_valid_report_no_not_flagged(self):
        """合规编号不应被标记。"""
        summary = _format_summary({"report_no": "JC2026-0431"})
        assert "待核对" not in summary
