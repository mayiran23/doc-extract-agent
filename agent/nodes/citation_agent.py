"""Citation Agent — 从 PDF 文本提取引文元数据 + Crossref DOI 补全。

处理逻辑：
1. LLM 从前 4000 字符提取作者、标题、期刊、年份、卷期、页码、DOI
2. 若 DOI 未在文本中找到，通过 Crossref API 查询补全
3. 格式化为标准中文引文格式
"""

import json

import requests

from agent.state import ExtractionState
from agent.tools.llm_utils import call_llm
from config.settings import settings


def citation_agent(state: ExtractionState) -> dict:
    """从 PDF 文本提取引文元数据并生成标准引文。"""
    pdf_text = state.get("pdf_text", "")

    if not pdf_text:
        return {"citation": ""}

    text_head = pdf_text[:4000]

    # Step 1: LLM 提取元数据
    metadata = _extract_metadata(text_head)

    # Step 2: DOI 补全
    doi = metadata.get("doi", "")
    if not doi and metadata.get("title"):
        doi = _lookup_doi(metadata["title"], metadata.get("first_author", ""))
        metadata["doi"] = doi

    # Step 3: 格式化引文
    citation = _format_citation(metadata)

    return {"citation": citation}


def _extract_metadata(text_head: str) -> dict:
    """使用 LLM 从前 4000 字符提取文献元数据。"""
    prompt = f"""从以下PDF文本的开头部分提取文献元数据，以JSON格式返回：

{text_head}

返回JSON格式（缺失的字段用空字符串）：
{{
    "title": "文献标题",
    "first_author": "第一作者",
    "authors": "全部作者",
    "journal": "期刊名或学校名",
    "year": "发表年份",
    "volume": "卷号",
    "issue": "期号",
    "pages": "页码范围",
    "doi": "DOI（如文本中有）",
    "type": "J（期刊论文）或 D（学位论文）或 C（会议论文）"
}}

只返回JSON，不要其他内容。"""

    system = "你是一名文献元数据提取专家。只返回JSON。"
    try:
        response = call_llm(prompt, system=system)
        metadata = json.loads(response)
    except Exception:
        return {}

    return metadata


def _lookup_doi(title: str, author: str = "") -> str:
    """通过 Crossref API 查询 DOI。"""
    try:
        params = {"query.title": title, "rows": 3}
        if author:
            params["query.author"] = author

        resp = requests.get(
            settings.crossref_api_url,
            params=params,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("message", {}).get("items", [])
            if items:
                return items[0].get("DOI", "")
    except Exception:
        pass

    return ""


def _format_citation(metadata: dict) -> str:
    """格式化为标准中文引文格式。"""
    if not metadata or not metadata.get("title"):
        return ""

    authors = metadata.get("authors", metadata.get("first_author", ""))
    title = metadata.get("title", "")
    pub_type = metadata.get("type", "J")
    journal = metadata.get("journal", "")
    year = metadata.get("year", "")
    volume = metadata.get("volume", "")
    issue = metadata.get("issue", "")
    pages = metadata.get("pages", "")
    doi = metadata.get("doi", "")

    vol_issue_pages = ""
    if volume:
        vol_issue_pages += volume
    if issue:
        vol_issue_pages += f"({issue})"
    if pages:
        vol_issue_pages += f": {pages}"

    type_label = "J" if pub_type in ("J", "journal", "") else "D"
    citation = f"{authors}. {title}[{type_label}]"

    if journal:
        citation += f". {journal}"

    if year:
        citation += f", {year}"

    if vol_issue_pages:
        citation += f", {vol_issue_pages}"

    if doi:
        citation += f". DOI: {doi}"

    return citation.replace("..", ".").strip()
