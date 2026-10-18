"""Streamlit 应用 — 文献数据提取 Agent UI。

启动方式: streamlit run app.py
"""

import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

# ── 启动前检查 ──
from dotenv import load_dotenv
load_dotenv()

_ENV_PATH = Path(__file__).parent / ".env"
if not _ENV_PATH.exists():
    print("[提示] .env 文件不存在，可在 Streamlit 侧边栏输入 API Key")

if not os.getenv("DEEPSEEK_API_KEY"):
    print("[提示] DEEPSEEK_API_KEY 未设置 — 在侧边栏输入或创建 .env 文件")

st.set_page_config(page_title="文献数据提取 Agent", layout="wide")

from ui.components import (
    render_column_confirmation,
    render_pdf_upload_step,
    render_progress,
    render_results,
    render_sidebar,
    render_template_step,
)
from ui.session_state import init_session_state

init_session_state()
render_sidebar()

st.title("LangGraph 文献数据提取 Agent")
st.markdown("从学术 PDF 中自动提取结构化数据，生成格式化 Excel 表格")


@st.cache_resource
def load_graph():
    from agent.graph import build_graph
    return build_graph()


def _run_extraction():
    """执行批量提取流程。"""
    from agent.graph import build_graph
    from agent.tools.excel_writer import ExcelWriter

    uploaded = st.session_state.get("uploaded_pdfs", [])
    columns = st.session_state.get("columns", [])
    log = st.session_state.get("processing_log", [])

    temp_dir = tempfile.mkdtemp()
    pdf_paths = []
    for f in uploaded:
        path = os.path.join(temp_dir, f.name)
        with open(path, "wb") as fh:
            fh.write(f.getbuffer())
        pdf_paths.append(path)

    graph = build_graph()
    writer = ExcelWriter()
    all_rows = []

    for i, pdf_path in enumerate(pdf_paths):
        paper_name = os.path.basename(pdf_path)
        ts = datetime.now().strftime("%H:%M:%S")
        log.append((ts, f"[{i+1}/{len(pdf_paths)}] 处理: {paper_name}"))
        st.session_state["processing_log"] = log

        state = {
            "excel_path": "", "natural_language_query": "",
            "template_source": "natural_language",
            "columns": columns, "template_confirmed": True,
            "current_pdf": pdf_path, "current_paper_id": "",
            "pdf_text": "", "citation": "",
            "current_rows": [], "all_rows": [],
            "validation_passed": False, "validation_issues": [],
            "validation_detail": "", "extraction_hints": "",
            "reflection_rounds": 0, "error": None,
            "paper_completed": False, "notification": "",
        }

        try:
            result = graph.invoke(state, {"recursion_limit": 50})
            new_rows = result.get("all_rows", []) or result.get("current_rows", [])
            citation = result.get("citation", "")
            for row in new_rows:
                row["citation"] = citation
                row["paper_id"] = result.get("current_paper_id", paper_name)
            all_rows.extend(new_rows)
            ts = datetime.now().strftime("%H:%M:%S")
            log.append((ts, f"  完成: {paper_name} — {len(new_rows)} 行"))
        except Exception as e:
            ts = datetime.now().strftime("%H:%M:%S")
            log.append((ts, f"  错误: {paper_name} — {e}"))

        st.session_state["processing_log"] = log

    if all_rows:
        os.makedirs("output", exist_ok=True)
        output_path = os.path.join(
            "output",
            f"文献数据提取_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        )
        writer.write(all_rows, columns, output_path)
        st.session_state["output_path"] = output_path

    st.session_state["extraction_results"] = all_rows
    st.session_state["processing_complete"] = True

    ts = datetime.now().strftime("%H:%M:%S")
    log.append((ts, f"=== 完成，共 {len(all_rows)} 行 ==="))
    st.session_state["processing_log"] = log


step = st.session_state.get("step", 1)

if step == 1:
    result = render_template_step()
    if result.get("action") == "analyze_template":
        with st.spinner("正在分析模板..."):
            from agent.nodes.template_agent import template_agent

            source = result["source"]
            excel_path = ""

            if source == "excel":
                excel_bytes = st.session_state.get("excel_bytes")
                if not excel_bytes:
                    st.error("请先上传 Excel 模板文件")
                    st.stop()
                import tempfile
                suffix = os.path.splitext(
                    st.session_state.get("excel_filename", "template.xlsx")
                )[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp.write(excel_bytes)
                tmp.close()
                excel_path = tmp.name

            state = {
                "excel_path": excel_path,
                "natural_language_query": st.session_state.get("nl_query", ""),
                "template_source": source,
                "columns": [],
                "template_confirmed": False,
            }
            output = template_agent(state)
            if "error" in output:
                st.error(output["error"])
            else:
                st.session_state["columns"] = output.get("columns", [])
                st.session_state["step"] = 2
                st.rerun()

elif step == 2:
    result = render_column_confirmation()
    if result.get("action") == "columns_confirmed":
        st.success("列定义已确认！")
        st.session_state["step"] = 3
        st.rerun()

elif step == 3:
    result = render_pdf_upload_step()
    if result.get("action") == "start_extraction":
        st.session_state["step"] = 4
        st.rerun()

elif step == 4:
    if not st.session_state.get("processing_complete", False):
        with st.spinner("正在提取数据，请耐心等待（LLM 处理约需1-2分钟）..."):
            _run_extraction()
    render_progress()
    if st.session_state.get("processing_complete", False):
        render_results()
