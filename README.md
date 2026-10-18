# 单据结构化提取 Agent

基于 LangGraph + DeepSeek 的非结构化文档字段提取系统。上传 Excel 模板（或自然语言描述要哪些字段）+ PDF 单据，自动识别并抽取字段，输出结构化表格。

> **来源说明**：本项目架构参考 [gudaochangci/literature-extraction-agent](https://github.com/gudaochangci/literature-extraction-agent)（MIT），
> 在此基础上将业务域从「学术文献数据提取」改造为「单据字段提取」，并重写了校验规则与提示词。原始版权声明见 LICENSE。
>
> **TO-DO（自己填）**：业务域 = ______（例如：供应商报价单比价 / 检测报告数据归档 / 合同关键条款提取）

## 架构

```
template_agent → reading_agent → citation_agent → extraction_agent
                                                        │
                                              ┌─────────┼──────────┐
                                              │ pass     │ reflect  │
                                              ▼          ▼          │
                                             END   reflection_engine│
                                                     │             │
                                                     └───────loop──┘
```

**6 个 Node（串行，条件循环）：**

| Node | 职责 |
|------|------|
| Template Agent | 理解用户数据需求 → 列定义（Excel 模式列名原样保留） |
| Reading Agent | PDF → 纯文本（pdfplumber，全文保留） |
| Citation Agent | 提取文献元数据 → 标准引文格式（含 DOI，Crossref 补全） |
| Extraction Agent | **分块全量提取**：全文均匀分块 → 每块 LLM 提取 → 合并去重 |
| Validation Engine | 四级规则检查（completeness/plausibility/consistency/traceability） |
| Reflection Engine | 分析验证失败原因 → 生成修正策略 → 循环重试 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key
```

```
DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-v4-flash
```

> 兼容 OpenAI API，如需使用 OpenAI，修改 `DEEPSEEK_BASE_URL` 和 `MODEL_NAME` 即可。

### 3. 启动

**Streamlit Web UI（推荐）：**

```bash
streamlit run app.py
```

四步流程：定义需求 → 确认列定义 → 上传 PDF → 下载 Excel。

**命令行：**

```bash
# 自然语言描述需求
python main.py --query "提取TS、VS、pH、温度、沼气产量" --pdfs ./papers/

# 上传 Excel 模板
python main.py --template template.xlsx --pdfs ./papers/ -o result.xlsx
```

## 提取策略

**分块全量提取**（不依赖正则定位数据位置）：

```
全文 → 均匀分块(每~10K) → 每块独立LLM提取 → 合并去重 → 输出
```

- 摘要在第 1 块 → LLM 自己找到
- 结论在最后一块 → LLM 自己找到
- 正文表格在中间 → LLM 自己找到

## 项目结构

```
├── app.py                    # Streamlit UI 入口
├── main.py                   # CLI 批量处理入口
├── config/settings.py        # 全局配置
├── agent/
│   ├── state.py              # 状态定义（TypedDict）
│   ├── graph.py              # LangGraph 图构建
│   ├── nodes/                # 6 个 Agent Node
│   │   ├── template_agent.py
│   │   ├── reading_agent.py
│   │   ├── citation_agent.py
│   │   ├── extraction_agent.py
│   │   ├── validation_engine.py
│   │   └── reflection_engine.py
│   └── tools/                # 工具层
│       ├── pdf_parser.py     # pdfplumber 封装
│       ├── excel_reader.py   # Excel 读取
│       ├── excel_writer.py   # 格式化 Excel 输出
│       └── llm_utils.py      # LLM 调用 + JSON 解析
├── prompts/                  # 提示词模板
├── ui/                       # Streamlit 组件
└── tests/                    # 84 个测试
```

## 技术栈

- **LangGraph** — Agent 编排
- **langchain-openai** — LLM 调用（兼容 OpenAI/DeepSeek）
- **pdfplumber** — PDF 文本提取
- **openpyxl** — Excel 读写
- **Streamlit** — Web UI

## License

MIT
