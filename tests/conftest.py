"""pytest 共享 fixture — mock LLM、样本数据、初始 State。"""

import os
import tempfile
from typing import Dict, List
from unittest.mock import MagicMock

import pytest

# 确保项目根目录在 sys.path 中
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══ 样本数据 ═══

SAMPLE_COLUMN_NAMES = [
    "序号", "厌氧发酵类型", "原料", "接种物", "含水率%（MC）",
    "TS", "VS", "VS/TS", "灰分%", "温度(°C)", "pH", "反应时间(d)",
    "HRT (d)", "OLR (g VS/L/d)", "搅拌", "C", "H", "O", "N", "TAN",
    "S", "C/N", "VFA", "F/I（底物与接种物比率）", "SCOD (mg/L)",
    "接种流模式", "生物炭投加量BD (g/L)", "热值（KJ/g）",
    "沼气产量(ml/kg)", "沼气产量（m3/kg TS）", "沼气产量（m3/kg VS）",
    "甲烷产量/含量", "影响因素相关性分析", "数据来源", "图表", "图表2", "备注",
]

SAMPLE_PDF_TEXT = """--- Page 1 ---
Title: Anaerobic Co-digestion of Cattle Manure and Corn Straw

Abstract:
This study investigated the anaerobic co-digestion of cattle manure and
corn straw under mesophilic conditions (37°C). The total solids (TS)
content of the feedstock was 8.5%, with a volatile solids (VS) content
of 82.3% of TS. The pH was maintained at 7.2 throughout the experiment.

--- Page 2 ---
Table 1: Feedstock characteristics
Parameter          Value
TS (%)             8.5
VS (% of TS)       82.3
pH                 7.2
C/N ratio          25.3

--- Page 3 ---
Table 2: Biogas production results
Treatment          Biogas yield (mL/g VS)    CH4 content (%)
T1 (control)       280                       55
T2 (CM:CS=3:1)     320                       58
T3 (CM:CS=1:1)     350                       62
"""


# ═══ Fixture ═══


@pytest.fixture
def sample_pdf_text() -> str:
    """模拟一篇厌氧发酵文献的提取文本。"""
    return SAMPLE_PDF_TEXT


@pytest.fixture
def sample_column_names() -> List[str]:
    """37 列厌氧发酵模板的表头。"""
    return SAMPLE_COLUMN_NAMES


@pytest.fixture
def sample_columns() -> List[Dict]:
    """模拟 Template Agent 输出的 ColumnDef 列表（精简版，仅 4 列）。"""
    return [
        {"col_name": "TS", "semantic_type": "substrate_property",
         "unit": "%", "description": "总固体含量", "expected_range": "0-100"},
        {"col_name": "VS", "semantic_type": "substrate_property",
         "unit": "%", "description": "挥发性固体含量", "expected_range": "0-100"},
        {"col_name": "pH", "semantic_type": "condition",
         "unit": "", "description": "pH值", "expected_range": "0-14"},
        {"col_name": "温度(°C)", "semantic_type": "condition",
         "unit": "°C", "description": "反应温度", "expected_range": "20-60"},
        {"col_name": "沼气产量(ml/kg)", "semantic_type": "gas_production",
         "unit": "ml/kg", "description": "单位质量沼气产量", "expected_range": "0-1000"},
    ]


@pytest.fixture
def sample_data_rows() -> List[Dict]:
    """模拟 Extraction Agent 输出的 DataRow 列表。"""
    return [
        {
            "paper_id": "sample_paper",
            "sequence_id": "A1",
            "values": {"TS": "8.5", "VS": "82.3", "pH": "7.2", "温度(°C)": "37",
                       "沼气产量(ml/kg)": "280"},
            "source_table": "Table 1",
            "source_figure": "",
            "notes": "",
        },
        {
            "paper_id": "sample_paper",
            "sequence_id": "A2",
            "values": {"TS": "8.5", "VS": "82.3", "pH": "7.2", "温度(°C)": "37",
                       "沼气产量(ml/kg)": "320"},
            "source_table": "Table 2",
            "source_figure": "",
            "notes": "T2 treatment: CM:CS=3:1",
        },
    ]


@pytest.fixture
def base_state() -> Dict:
    """初始 ExtractionState — 模拟一篇文献处理前的状态。"""
    from agent.state import ExtractionState

    return {
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


@pytest.fixture
def mock_llm_response():
    """创建模拟 LLM 响应的工厂函数。"""

    def _make_response(content: str) -> MagicMock:
        mock = MagicMock()
        mock.content = content
        return mock

    return _make_response


@pytest.fixture
def temp_dir():
    """临时目录 — 测试用，自动清理。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
