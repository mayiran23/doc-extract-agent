"""CLI 批量处理入口 — 从命令行运行检测报告数据提取。

用法:
    python main.py --template data/sample_template.xlsx --pdfs ./papers/
    python main.py --query "提取样品编号、检测项目、检测值、标准限值" --pdfs ./reports/
"""

import argparse
import glob
import os
import sys
from datetime import datetime

from agent.graph import build_graph
from agent.tools.excel_writer import ExcelWriter


def parse_args():
    parser = argparse.ArgumentParser(description="LangGraph 检测报告数据提取 Agent")
    template = parser.add_mutually_exclusive_group(required=True)
    template.add_argument("--template", "-t", type=str, help="Excel 模板路径")
    template.add_argument("--query", "-q", type=str, help="自然语言需求描述")
    parser.add_argument("--pdfs", "-p", type=str, required=True, help="PDF 目录路径")
    parser.add_argument("--output", "-o", type=str, default=None, help="输出路径")
    parser.add_argument("--max-rounds", "-r", type=int, default=3, help="最大反射轮次")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.template:
        template_source, excel_path, nl_query = "excel", args.template, ""
        print(f"[INFO] Excel 模板: {excel_path}")
    else:
        template_source, excel_path, nl_query = "natural_language", "", args.query
        print(f"[INFO] NL 查询: {nl_query}")

    pdf_pattern = os.path.join(args.pdfs, "*.pdf")
    pdf_files = sorted(glob.glob(pdf_pattern))
    if not pdf_files:
        print(f"[ERROR] 未找到 PDF: {pdf_pattern}")
        sys.exit(1)
    print(f"[INFO] {len(pdf_files)} 份报告")

    output_path = args.output or os.path.join(
        "output", f"检测报告数据提取_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    print("[INFO] 编译 LangGraph...")
    graph = build_graph()

    print("[INFO] 分析模板...")
    init_state = {
        "excel_path": excel_path, "natural_language_query": nl_query,
        "template_source": template_source,
        "columns": [], "template_confirmed": False,
        "current_pdf": "", "current_paper_id": "",
        "pdf_text": "", "citation": "",
        "current_rows": [], "all_rows": [],
        "validation_passed": False, "validation_issues": [],
        "validation_detail": "", "extraction_hints": "",
        "reflection_rounds": 0, "error": None,
        "paper_completed": False, "notification": "",
    }

    result = graph.invoke(init_state, {"recursion_limit": 50})
    columns = result.get("columns", [])

    if not columns:
        print("[ERROR] 模板分析失败")
        sys.exit(1)

    print(f"[INFO] 识别 {len(columns)} 列")

    writer = ExcelWriter()
    all_rows = []

    for i, pdf in enumerate(pdf_files):
        paper_name = os.path.basename(pdf)
        print(f"\n[{i+1}/{len(pdf_files)}] 处理: {paper_name}")

        state = {
            "excel_path": excel_path, "natural_language_query": nl_query,
            "template_source": template_source,
            "columns": columns, "template_confirmed": True,
            "current_pdf": pdf, "current_paper_id": "",
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
            print(f"  [OK] {len(new_rows)} 行")
        except Exception as e:
            print(f"  [ERROR] {e}")

    if all_rows:
        writer.write(all_rows, columns, output_path)
        print(f"\n=== 完成: {len(pdf_files)} 报告, {len(all_rows)} 行 ===")
        print(f"结果: {output_path}")
    else:
        print("\n[WARN] 未提取到数据")
        sys.exit(1)


if __name__ == "__main__":
    main()
