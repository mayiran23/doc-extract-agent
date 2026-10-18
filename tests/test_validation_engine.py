"""Test agent/nodes/validation_engine.py — 四级质量检查。"""

from agent.nodes.validation_engine import _rule_check, validation_engine

SAMPLE_COLS = [
    {"col_name": "铅含量", "semantic_type": "measured_value",
     "unit": "mg/L", "expected_range": "0-1"},
    {"col_name": "pH", "semantic_type": "measured_value",
     "unit": "", "expected_range": "0-14"},
]


class TestValidationEngine:
    """Validation Engine 测试。"""

    def test_empty_rows_passes(self):
        """空数据应直接通过。"""
        result = validation_engine({"current_rows": [], "columns": []})
        assert result["validation_passed"] is True

    def test_valid_data_passes_rule_check(self):
        """合理数据应通过规则检查。"""
        rows = [{"values": {"铅含量": "0.05", "pH": "7.2"},
                 "source_table": "检测结果表"}]
        issues = _rule_check(rows, SAMPLE_COLS)
        has_errors = any(i["severity"] == "error" for i in issues)
        assert not has_errors

    def test_ph_out_of_range_fails(self):
        """pH 超出范围应返回 error。"""
        rows = [{"values": {"铅含量": "0.05", "pH": "15.0"},
                 "source_table": "检测结果表"}]
        issues = _rule_check(rows, SAMPLE_COLS)
        ph_issues = [i for i in issues if i["column"] == "pH"]
        assert len(ph_issues) > 0
        assert ph_issues[0]["severity"] == "error"

    def test_value_out_of_range_fails(self):
        """检测值超出 expected_range 应返回 error。"""
        rows = [{"values": {"铅含量": "150", "pH": "7.0"},
                 "source_table": "检测结果表"}]
        issues = _rule_check(rows, SAMPLE_COLS)
        lead_issues = [i for i in issues if i["column"] == "铅含量"]
        assert len(lead_issues) > 0
        assert lead_issues[0]["severity"] == "error"

    def test_negative_measured_value_fails(self):
        """检测值为负应返回 error（measured_value 不允许为负）。"""
        rows = [{"values": {"铅含量": "-0.5", "pH": "7.0"},
                 "source_table": "检测结果表"}]
        issues = _rule_check(rows, SAMPLE_COLS)
        lead_issues = [i for i in issues if i["column"] == "铅含量"]
        assert len(lead_issues) > 0
        assert lead_issues[0]["severity"] == "error"

    def test_missing_source_warns(self):
        """有数据但无来源应产生 warning。"""
        rows = [{"values": {"铅含量": "0.05", "pH": "7.2"}}]
        issues = _rule_check(rows, SAMPLE_COLS)
        trace_issues = [i for i in issues if i["level"] == "traceability"]
        assert len(trace_issues) > 0

    def test_multi_row_consistency_reminder(self):
        """多行数据应触发一致性提醒。"""
        rows = [
            {"values": {"铅含量": "0.05", "pH": "7.2"}, "source_table": "检测结果表"},
            {"values": {"铅含量": "0.06", "pH": "7.3"}, "source_table": "检测结果表"},
        ]
        issues = _rule_check(rows, SAMPLE_COLS)
        consist = [i for i in issues if i["level"] == "consistency"]
        assert len(consist) > 0

    def test_non_numeric_value_ignored(self):
        """「未检出」这类非数值不触发合理性检查，也不报错。"""
        rows = [{"values": {"铅含量": "未检出", "pH": "7.2"},
                 "source_table": "检测结果表"}]
        issues = _rule_check(rows, SAMPLE_COLS)
        lead_issues = [i for i in issues if i["column"] == "铅含量"
                       and i["level"] == "plausibility"]
        assert lead_issues == []
