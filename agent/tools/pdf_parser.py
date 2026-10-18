"""PDF 文本提取 — pdfplumber 封装。

提供两个主要接口：
- extract_text: 逐页提取纯文本，加页码标记
- extract_tables: 提取所有表格（结构化数据）
"""

from typing import List, Optional

import pdfplumber


def extract_text(pdf_path: str, max_pages: int = 100) -> str:
    """从 PDF 文件中提取纯文本，每页加 `--- Page N ---` 标记。

    Args:
        pdf_path: PDF 文件的绝对路径。
        max_pages: 安全上限，超过此页数的 PDF 截断处理。

    Returns:
        带页码标记的完整文本。如果整个 PDF 都是扫描版（无提取文本），返回空字符串。

    Raises:
        FileNotFoundError: PDF 文件不存在。
        ValueError: PDF 文件已加密或损坏无法打开。
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text_parts: List[str] = []
            page_count = min(len(pdf.pages), max_pages)

            for i in range(page_count):
                page = pdf.pages[i]
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

            return "\n\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"无法读取PDF文件 {pdf_path}: {e}") from e


def extract_tables(pdf_path: str, max_pages: int = 100) -> List[List[List[Optional[str]]]]:
    """从 PDF 中提取所有表格（结构化二维数组）。

    Args:
        pdf_path: PDF 文件的绝对路径。
        max_pages: 安全上限。

    Returns:
        三层嵌套列表：每页 → 每表 → 每行 → 每单元格的值。
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_tables: List[List[List[Optional[str]]]] = []
            page_count = min(len(pdf.pages), max_pages)

            for i in range(page_count):
                page = pdf.pages[i]
                page_tables = page.extract_tables()
                if page_tables:
                    all_tables.append(page_tables)

            return all_tables
    except Exception as e:
        raise ValueError(f"无法提取PDF表格 {pdf_path}: {e}") from e


def is_scanned_pdf(pdf_path: str) -> bool:
    """检测 PDF 是否为扫描版（无可提取的文本层）。

    Args:
        pdf_path: PDF 文件的绝对路径。

    Returns:
        True 表示 PDF 是扫描版（文本少于 100 字符）。
    """
    text = extract_text(pdf_path)
    return len(text.strip()) < 100
