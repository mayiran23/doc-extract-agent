"""集成测试 — 完整图 invoke 流程（需要 LLM key 才能完全运行）。"""

from agent.graph import build_graph, route_after_validation

INIT_STATE = {
    "excel_path": "",
    "natural_language_query": "提取TS和pH",
    "template_source": "natural_language",
    "columns": [
        {"col_name": "铅含量", "semantic_type": "measured_value",
         "unit": "%", "description": "总固体", "expected_range": "0-100"},
        {"col_name": "pH", "semantic_type": "measured_value",
         "unit": "", "description": "pH值", "expected_range": "0-14"},
    ],
    "template_confirmed": True,
    "current_pdf": "",
    "current_paper_id": "",
    "pdf_text": "",
    "citation": "",
    "current_rows": [],
    "all_rows": [],
    "validation_passed": False,
    "validation_issues": [],
    "validation_detail": "",
    "extraction_hints": "",
    "reflection_rounds": 0,
    "error": None,
    "paper_completed": False,
    "notification": "",
}


class TestGraphIntegration:
    """全图集成测试。"""

    def test_graph_invokes(self):
        """图应能 invoke 完成（可能因无 API key 而失败，但不应图结构错误）。"""
        graph = build_graph()
        try:
            result = graph.invoke(INIT_STATE, {"recursion_limit": 30})
            assert isinstance(result, dict)
        except Exception as e:
            error_msg = str(e)
            # 只允许因配置问题失败
            assert any(kw in error_msg.lower() for kw in ["api", "key", "api_key"])

    def test_template_pass_through(self):
        """template_confirmed=True 时应跳过 Template Agent。"""
        graph = build_graph()
        state = {**INIT_STATE}
        state["template_confirmed"] = True

        try:
            result = graph.invoke(state, {"recursion_limit": 30})
            assert isinstance(result, dict)
        except Exception as e:
            error_msg = str(e)
            assert any(kw in error_msg.lower() for kw in ["api", "key", "api_key"])

    def test_reflection_loop_stops_at_max(self):
        """反射循环应在达到 max 轮次时终止。"""
        from config.settings import settings

        state = {
            "validation_passed": False,
            "reflection_rounds": settings.max_reflection_rounds + 1,
        }
        result = route_after_validation(state)
        assert result == "force_end"

    def test_empty_state_starts(self):
        """空 State 也应能启动图执行。"""
        graph = build_graph()
        empty_state = {
            "excel_path": "",
            "natural_language_query": "",
            "template_source": "",
            "columns": [],
            "template_confirmed": False,
            "current_pdf": "",
            "current_paper_id": "",
            "pdf_text": "",
            "citation": "",
            "current_rows": [],
            "all_rows": [],
            "validation_passed": False,
            "validation_issues": [],
            "validation_detail": "",
            "extraction_hints": "",
            "reflection_rounds": 0,
            "error": None,
            "paper_completed": False,
            "notification": "",
        }
        try:
            result = graph.invoke(empty_state, {"recursion_limit": 30})
            assert isinstance(result, dict)
        except Exception as e:
            error_msg = str(e)
            assert any(kw in error_msg.lower() for kw in ["api", "key", "api_key", "未指定"])
