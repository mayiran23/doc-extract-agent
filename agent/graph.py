"""LangGraph 图构建 — 注册所有 6 个 Node，定义边和条件路由。

核心流程（串行）：
template_agent → reading_agent → meta_agent → extraction_agent → validation_engine
                                                                          │
                                              ┌───────────────────────────┤
                                              │ pass/force_end            │ reflect
                                              ▼                           ▼
                                             END                  reflection_engine
                                                                          │
                                                                          ▼
                                                                  extraction_agent (loop)
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from agent.state import ExtractionState
from config.settings import settings

# ── 节点导入 ──
from agent.nodes.template_agent import template_agent
from agent.nodes.reading_agent import reading_agent
from agent.nodes.meta_agent import meta_agent
from agent.nodes.extraction_agent import extraction_agent
from agent.nodes.validation_engine import validation_engine
from agent.nodes.reflection_engine import reflection_engine

# 预定义所有节点名称
NODE_TEMPLATE = "template_agent"
NODE_READING = "reading_agent"
NODE_META = "meta_agent"
NODE_EXTRACTION = "extraction_agent"
NODE_VALIDATION = "validation_engine"
NODE_REFLECTION = "reflection_engine"


def route_after_validation(
    state: ExtractionState,
) -> Literal["pass", "reflect", "force_end"]:
    """Validation 之后的条件路由。

    - validation_passed → END
    - 未通过 且 未达最大轮次 → reflection_engine（继续循环）
    - 未通过 且 已达最大轮次 → END（强制终止）
    """
    if state.get("validation_passed", False):
        return "pass"

    max_rounds = settings.max_reflection_rounds
    current_rounds = state.get("reflection_rounds", 0)

    if current_rounds >= max_rounds:
        return "force_end"

    return "reflect"


def build_graph() -> StateGraph:
    """构建 LangGraph 图，注册所有节点和边。

    Returns:
        编译后的 CompiledGraph。
    """
    builder = StateGraph(ExtractionState)

    # ── 注册所有 6 个 Node ──
    builder.add_node(NODE_TEMPLATE, template_agent)

    # Stub nodes — 占位，后续 Step 逐步替换为实际实现
    builder.add_node(NODE_READING, reading_agent)
    builder.add_node(NODE_META, meta_agent)
    builder.add_node(NODE_EXTRACTION, extraction_agent)
    builder.add_node(NODE_VALIDATION, validation_engine)
    builder.add_node(NODE_REFLECTION, reflection_engine)

    # ── 串行边 ──
    builder.set_entry_point(NODE_TEMPLATE)
    builder.add_edge(NODE_TEMPLATE, NODE_READING)
    builder.add_edge(NODE_READING, NODE_META)
    builder.add_edge(NODE_META, NODE_EXTRACTION)
    builder.add_edge(NODE_EXTRACTION, NODE_VALIDATION)

    # ── 条件边：Validation → END 或 Reflection ──
    builder.add_conditional_edges(
        NODE_VALIDATION,
        route_after_validation,
        {
            "pass": END,
            "reflect": NODE_REFLECTION,
            "force_end": END,
        },
    )

    # ── Reflection → Extraction（循环）──
    builder.add_edge(NODE_REFLECTION, NODE_EXTRACTION)

    return builder.compile()
