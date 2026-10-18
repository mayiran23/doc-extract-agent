"""Test agent/graph.py — 图编译、节点注册、条件路由逻辑。"""

import pytest
from langgraph.graph import END

from agent.graph import (
    NODE_TEMPLATE,
    NODE_READING,
    NODE_CITATION,
    NODE_EXTRACTION,
    NODE_VALIDATION,
    NODE_REFLECTION,
    build_graph,
    route_after_validation,
)


class TestGraphCompilation:
    """图编译测试。"""

    def test_graph_compiles(self):
        """build_graph() 应返回 CompiledGraph 无异常。"""
        graph = build_graph()
        assert graph is not None
        assert hasattr(graph, "invoke")

    def test_graph_has_all_nodes(self):
        """图应注册全部 6 个节点。"""
        graph = build_graph()
        nodes = graph.get_graph().nodes
        node_names = {n for n in nodes.keys()}
        expected = {
            NODE_TEMPLATE,
            NODE_READING,
            NODE_CITATION,
            NODE_EXTRACTION,
            NODE_VALIDATION,
            NODE_REFLECTION,
        }
        assert expected.issubset(node_names), f"缺少节点: {expected - node_names}"


class TestRouteAfterValidation:
    """条件路由测试。"""

    def test_pass_when_validated(self):
        """验证通过时应返回 'pass'。"""
        state = {"validation_passed": True, "reflection_rounds": 0}
        result = route_after_validation(state)
        assert result == "pass"

    def test_reflect_when_not_passed_under_max(self):
        """未通过且未达上限时应返回 'reflect'。"""
        state = {"validation_passed": False, "reflection_rounds": 0}
        result = route_after_validation(state)
        assert result == "reflect"

    def test_force_end_when_max_rounds_exceeded(self):
        """未通过且已达最大轮次时应返回 'force_end'。"""
        from config.settings import settings

        max_rounds = settings.max_reflection_rounds
        state = {"validation_passed": False, "reflection_rounds": max_rounds}
        result = route_after_validation(state)
        assert result == "force_end"

    def test_force_end_when_over_max(self):
        """超过最大轮次时也应返回 'force_end'。"""
        from config.settings import settings

        max_rounds = settings.max_reflection_rounds
        state = {"validation_passed": False, "reflection_rounds": max_rounds + 5}
        result = route_after_validation(state)
        assert result == "force_end"

    def test_missing_keys_defaults(self):
        """缺失关键字段时使用合理默认值。"""
        result = route_after_validation({})
        assert result == "reflect"  # 默认未通过，轮次 0
