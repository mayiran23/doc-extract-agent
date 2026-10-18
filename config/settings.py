"""应用配置 — 从环境变量加载，提供默认值。"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """全局配置单例，通过 Settings.from_env() 创建。"""

    # LLM 配置（默认使用 DeepSeek，兼容 OpenAI 协议）
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "")
    )
    deepseek_base_url: str = field(
        default_factory=lambda: os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )
    )
    model_name: str = field(
        default_factory=lambda: os.getenv("MODEL_NAME", "deepseek-v4-flash")
    )
    llm_temperature: float = 0.0  # 确定性提取，零温度
    llm_max_tokens: int = 4096

    # Reflection 控制
    max_reflection_rounds: int = field(
        default_factory=lambda: int(os.getenv("MAX_REFLECTION_ROUNDS", "3"))
    )

    # 路径配置
    output_dir: str = field(
        default_factory=lambda: os.getenv("OUTPUT_DIR", "./output")
    )
    temp_dir: str = field(
        default_factory=lambda: os.getenv("TEMP_DIR", "./data")
    )

    # PDF 处理
    pdf_max_pages: int = 100  # 安全上限
    pdf_chunk_size: int = 10000  # 分块提取时每块的字符数
    pdf_max_chunks: int = 8  # 单份报告最多处理的块数（限制 API 调用量）


    @classmethod
    def from_env(cls) -> "Settings":
        """从环境变量创建配置实例。"""
        return cls()


# 全局单例
settings = Settings.from_env()
