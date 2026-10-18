"""Reading Agent — 从 PDF 提取纯文本。

处理逻辑：
- 调用 pdfplumber 逐页提取文本，加 `--- Page N ---` 标记
- 派生 paper_id（从文件名去扩展名，清理特殊字符）
- 检测扫描版 PDF，设置 error 字段
- 保留全文，不再硬截断（由 Extraction Agent 智能分段处理）
"""

from agent.state import ExtractionState
from agent.tools.pdf_parser import extract_text, is_scanned_pdf
from config.settings import settings


def reading_agent(state: ExtractionState) -> dict:
    """从当前 PDF 提取全文并写入 State。"""
    pdf_path = state.get("current_pdf", "")

    if not pdf_path:
        return {"error": "未指定 PDF 文件路径 (current_pdf 为空)"}

    # 派生 paper_id
    paper_id = pdf_path.split("\\")[-1].split("/")[-1]
    if "." in paper_id:
        paper_id = ".".join(paper_id.split(".")[:-1])
    paper_id = paper_id.replace(" ", "_")

    # 检测扫描版 PDF
    if is_scanned_pdf(pdf_path):
        return {
            "pdf_text": "",
            "current_paper_id": paper_id,
            "error": f"PDF 为扫描版，无可提取文本: {pdf_path}",
            "notification": f"跳过扫描版 PDF: {paper_id}",
        }

    # 提取全文（不截断！）
    try:
        text = extract_text(pdf_path, max_pages=settings.pdf_max_pages)
    except (FileNotFoundError, ValueError) as e:
        return {
            "pdf_text": "",
            "current_paper_id": paper_id,
            "error": str(e),
            "notification": f"读取 PDF 失败: {paper_id}",
        }

    notification = f"已读取 {paper_id}（{len(text)} 字符）"

    return {
        "pdf_text": text,
        "current_paper_id": paper_id,
        "notification": notification,
    }
