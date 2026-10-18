"""Test agent/nodes/reflection_engine.py — 修正策略生成。"""

from agent.nodes.reflection_engine import (
    _fallback_hints,
    _format_issues,
    reflection_engine,
)


class TestReflectionEngine:
    """Reflection Engine 测试。"""

    def test_empty_issues_returns_empty_hints(self):
        """无问题时不应生成 hints。"""
        state = {
            "validation_issues": [],
            "current_rows": [],
            "columns": [],
            "pdf_text": "",
            "reflection_rounds": 0,
        }
        result = reflection_engine(state)
        assert result["extraction_hints"] == ""
        assert result["reflection_rounds"] == 1

    def test_rounds_increment(self):
        """每调用一次 reflection_rounds 应+1。"""
        state = {"validation_issues": [], "reflection_rounds": 2}
        result = reflection_engine(state)
        assert result["reflection_rounds"] == 3


class TestFallbackHints:
    """降级 hints 生成测试。"""

    def test_plausibility_hint(self):
        """合理性问题的 hint 应包含具体指引。"""
        issues = [{
            "level": "plausibility", "column": "pH", "row_index": 0,
            "description": "pH值 15 超出范围", "severity": "error",
        }]
        hints = _fallback_hints(issues)
        assert "pH" in hints or "15" in hints
        assert "小数点" in hints or "单位" in hints

    def test_completeness_hint(self):
        """完整性问题的 hint 应建议扫描全文。"""
        issues = [{
            "level": "completeness", "column": "VS", "row_index": 0,
            "description": "VS 列未填充但文献中有报告", "severity": "warning",
        }]
        hints = _fallback_hints(issues)
        assert "扫描" in hints or "全文" in hints or "遗漏" in hints


class TestFormatIssues:
    """问题格式化测试。"""

    def test_format_issues(self):
        """问题应正确格式化为编号列表。"""
        issues = [
            {"level": "plausibility", "column": "pH", "row_index": 0,
             "description": "pH异常", "severity": "error"},
        ]
        text = _format_issues(issues)
        assert "1." in text
        assert "ERROR" in text or "error" in text
        assert "pH" in text
