"""Test agent/nodes/validation_engine.py — 四级质量检查。"""

from agent.nodes.validation_engine import _rule_check, validation_engine

SAMPLE_COLS = [
    {"col_name": "TS", "semantic_type": "substrate_property", "unit": "%"},
    {"col_name": "pH", "semantic_type": "condition", "unit": ""},
]


class TestValidationEngine:
    """Validation Engine 测试。"""

    def test_empty_rows_passes(self):
        """空数据应直接通过。"""
        result = validation_engine({"current_rows": [], "columns": []})
        assert result["validation_passed"] is True

    def test_valid_data_passes_rule_check(self):
        """合理数据应通过规则检查。"""
        rows = [{"values": {"TS": "8.5", "pH": "7.2"},
                 "source_table": "Table 1"}]
        issues = _rule_check(rows, SAMPLE_COLS)
        has_errors = any(i["severity"] == "error" for i in issues)
        assert not has_errors

    def test_ph_out_of_range_fails(self):
        """pH 超出范围应返回 error。"""
        rows = [{"values": {"TS": "8.5", "pH": "15.0"},
                 "source_table": "Table 1"}]
        issues = _rule_check(rows, SAMPLE_COLS)
        ph_issues = [i for i in issues if i["column"] == "pH"]
        assert len(ph_issues) > 0
        assert ph_issues[0]["severity"] == "error"

    def test_ts_out_of_range_fails(self):
        """TS 超出范围应返回 error。"""
        rows = [{"values": {"TS": "150", "pH": "7.0"},
                 "source_table": "Table 1"}]
        issues = _rule_check(rows, SAMPLE_COLS)
        ts_issues = [i for i in issues if i["column"] == "TS"]
        assert len(ts_issues) > 0
        assert ts_issues[0]["severity"] == "error"

    def test_missing_source_warns(self):
        """有数据但无来源应产生 warning。"""
        rows = [{"values": {"TS": "8.5", "pH": "7.2"}}]
        issues = _rule_check(rows, SAMPLE_COLS)
        trace_issues = [i for i in issues if i["level"] == "traceability"]
        assert len(trace_issues) > 0

    def test_multi_row_consistency_reminder(self):
        """多行数据应触发一致性提醒。"""
        rows = [
            {"values": {"TS": "8.5", "pH": "7.2"}, "source_table": "T1"},
            {"values": {"TS": "8.5", "pH": "7.3"}, "source_table": "T2"},
        ]
        issues = _rule_check(rows, SAMPLE_COLS)
        consist = [i for i in issues if i["level"] == "consistency"]
        assert len(consist) > 0
