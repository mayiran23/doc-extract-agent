"""Streamlit 会话状态管理。"""

import streamlit as st


def init_session_state():
    """初始化所有会话状态键。"""
    defaults = {
        "step": 1,
        "columns": [],
        "columns_confirmed": False,
        "template_source": "",
        "excel_path": "",
        "nl_query": "",
        "uploaded_pdfs": [],
        "pdf_temp_paths": [],
        "extraction_results": [],
        "processing_log": [],
        "processing_complete": False,
        "output_path": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session():
    """重置会话状态。"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session_state()
