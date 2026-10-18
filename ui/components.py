"""Streamlit 可复用 UI 组件。"""

import os

import streamlit as st


def render_sidebar():
    """侧边栏 — API 配置和参数。"""
    with st.sidebar:
        st.header("配置")

        # 检查 API Key 是否已配置
        has_env_key = bool(os.getenv("DEEPSEEK_API_KEY"))
        has_session_key = bool(st.session_state.get("api_key"))

        if not has_env_key and not has_session_key:
            st.warning("请设置 DeepSeek API Key")

        api_key = st.text_input(
            "DeepSeek API Key", type="password",
            value=os.getenv("DEEPSEEK_API_KEY", ""),
            help="留空使用 .env 中的 DEEPSEEK_API_KEY",
        )
        if api_key:
            st.session_state["api_key"] = api_key
            # 注入环境变量，使 Agent 能读取到
            os.environ["DEEPSEEK_API_KEY"] = api_key

        st.selectbox("模型", ["deepseek-v4-flash", "deepseek-v4"], index=0,
                      key="model_select")
        st.slider("最大反射轮次", 1, 5, 3, key="max_rounds")

        st.divider()
        st.caption("检测报告数据提取 Agent v1.0")
        st.caption("基于 LangGraph")


def render_template_step() -> dict:
    """Step 1: 定义数据需求。"""
    st.header("Step 1: 定义数据需求")

    tab_a, tab_b = st.tabs(["上传 Excel 模板", "自然语言描述"])

    with tab_a:
        uploaded = st.file_uploader("上传 Excel 模板 (.xlsx/.xls)", type=["xlsx", "xls"], key="tmpl_upload")
        if uploaded:
            st.success(f"已上传: {uploaded.name}")
            st.session_state["template_source"] = "excel"
            st.session_state["excel_filename"] = uploaded.name
            st.session_state["excel_bytes"] = uploaded.getvalue()
        if st.button("分析 Excel 模板", type="primary", key="btn_excel"):
            return {"action": "analyze_template", "source": "excel"}

    with tab_b:
        nl = st.text_area("描述需要提取的数据", placeholder="例如：提取样品编号、检测项目、检测值、单位、标准限值、判定结论...",
                           height=100, key="nl_input")
        if nl:
            st.session_state["nl_query"] = nl
        if st.button("分析需求", type="primary", key="btn_nl"):
            return {"action": "analyze_template", "source": "natural_language"}

    return {"action": None}


def render_column_confirmation() -> dict:
    """Step 2: 确认列定义。"""
    st.header("Step 2: 确认列定义")

    columns = st.session_state.get("columns", [])
    if not columns:
        st.warning("尚未分析模板，请返回 Step 1。")
        return {"action": None}

    st.info(f"已识别 {len(columns)} 列")

    edited = []
    for col in columns:
        edited.append({
            "列名": col.get("col_name", ""),
            "语义类型": col.get("semantic_type", ""),
            "单位": col.get("unit", ""),
            "说明": col.get("description", ""),
        })

    st.data_editor(edited, num_rows="dynamic", use_container_width=True, key="col_editor")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("确认并锁定", type="primary"):
            updated = []
            for row in edited:
                updated.append({
                    "col_name": row["列名"], "semantic_type": row["语义类型"],
                    "unit": row["单位"], "description": row["说明"],
                    "expected_range": "",
                })
            st.session_state["columns"] = updated
            st.session_state["columns_confirmed"] = True
            return {"action": "columns_confirmed"}
    with col2:
        if st.button("返回修改"):
            st.session_state["step"] = 1
            st.rerun()

    return {"action": None}


def render_pdf_upload_step() -> dict:
    """Step 3: 上传 PDF。"""
    st.header("Step 3: 上传 PDF 报告")

    uploaded = st.file_uploader("选择 PDF 报告（可多选）", type=["pdf"],
                                accept_multiple_files=True, key="pdf_up")
    if uploaded:
        st.session_state["uploaded_pdfs"] = uploaded
        st.success(f"已选择 {len(uploaded)} 份报告")
        for f in uploaded:
            st.text(f"  {f.name} ({f.size // 1024} KB)")

    col1, col2 = st.columns(2)
    with col1:
        disabled = not st.session_state.get("uploaded_pdfs")
        if st.button("开始提取", type="primary", disabled=disabled):
            return {"action": "start_extraction"}
    with col2:
        if st.button("返回修改列定义"):
            st.session_state["step"] = 2
            st.rerun()

    return {"action": None}


def render_progress():
    """Step 4a: 实时进度。"""
    st.header("提取进度")

    log = st.session_state.get("processing_log", [])
    total = len(st.session_state.get("uploaded_pdfs", []))
    progress_bar = st.progress(0)
    status_text = st.empty()

    if total > 0 and log:
        completed = sum(1 for e in log if "完成" in e[1])
        progress_bar.progress(min(completed / total, 1.0))
        status_text.text(f"处理中: {completed}/{total}")

    with st.expander("详细日志", expanded=True):
        for ts, msg in reversed(log[-20:]):
            st.text(f"[{ts}] {msg}")

    return log


def render_results():
    """Step 4b: 结果 + 下载。"""
    st.header("提取结果")

    results = st.session_state.get("extraction_results", [])
    total = len(st.session_state.get("uploaded_pdfs", []))

    col1, col2 = st.columns(2)
    col1.metric("处理报告数", total)
    col2.metric("提取数据行", len(results))

    if results:
        st.subheader("数据预览")
        cols = st.session_state.get("columns", [])
        col_names = ["paper_id", "sequence_id"] + [c["col_name"] for c in cols]
        preview = []
        for row in results[:50]:
            r = {"paper_id": row.get("paper_id", ""),
                 "sequence_id": row.get("sequence_id", "")}
            for c in cols:
                r[c["col_name"]] = row.get("values", {}).get(c["col_name"], "")
            preview.append(r)
        st.dataframe(preview, use_container_width=True)

    output_path = st.session_state.get("output_path", "")
    if output_path and st.session_state.get("processing_complete"):
        try:
            with open(output_path, "rb") as f:
                st.download_button(
                    "下载 Excel 结果", f,
                    file_name=output_path.split("/")[-1].split("\\")[-1],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                )
        except FileNotFoundError:
            st.warning("输出文件不存在")

    if st.button("开始新任务"):
        from ui.session_state import reset_session
        reset_session()
        st.rerun()
