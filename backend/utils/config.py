from enum import Enum
from typing import Dict, Any

class VectorDBProvider(str, Enum):
    MILVUS = "milvus",
    CHROMA = "chroma"
    # More providers can be added later

# Chroma HNSW 索引预设配置 — 用于索引对比分析
CHROMA_INDEX_PRESETS = {
    "cosine_default": {
        "name": "Cosine 默认参数（基线）",
        "metadata": {"hnsw:space": "cosine", "hnsw:M": 16, "hnsw:construction_ef": 100, "hnsw:search_ef": 10},
    },
    "cosine_high_recall": {
        "name": "Cosine 高召回率",
        "metadata": {"hnsw:space": "cosine", "hnsw:M": 64, "hnsw:construction_ef": 500, "hnsw:search_ef": 100},
    },
    "cosine_balanced": {
        "name": "Cosine 平衡型",
        "metadata": {"hnsw:space": "cosine", "hnsw:M": 32, "hnsw:construction_ef": 200, "hnsw:search_ef": 50},
    },
    "cosine_fast": {
        "name": "Cosine 快速构建/检索",
        "metadata": {"hnsw:space": "cosine", "hnsw:M": 8, "hnsw:construction_ef": 50, "hnsw:search_ef": 5},
    },
    "cosine_high_ef": {
        "name": "Cosine 高构建精度",
        "metadata": {"hnsw:space": "cosine", "hnsw:M": 16, "hnsw:construction_ef": 500, "hnsw:search_ef": 50},
    },
    "cosine_high_m": {
        "name": "Cosine 高连接度",
        "metadata": {"hnsw:space": "cosine", "hnsw:M": 64, "hnsw:construction_ef": 100, "hnsw:search_ef": 50},
    },
    "l2_default": {
        "name": "L2 距离基线",
        "metadata": {"hnsw:space": "l2", "hnsw:M": 16, "hnsw:construction_ef": 100, "hnsw:search_ef": 10},
    },
    "ip_default": {
        "name": "内积距离基线",
        "metadata": {"hnsw:space": "ip", "hnsw:M": 16, "hnsw:construction_ef": 100, "hnsw:search_ef": 10},
    },
}

# 可以在这里添加其他配置相关的内容
MILVUS_CONFIG = {
    "uri": "myrag",
    "index_types": {
        "flat": "FLAT",
        "ivf_flat": "IVF_FLAT",
        "ivf_sq8": "IVF_SQ8",
        "hnsw": "HNSW"
    },
    "index_params": {
        "flat": {},
        "ivf_flat": {"nlist": 1024},
        "ivf_sq8": {"nlist": 1024},
        "hnsw": {
            "M": 16,
            "efConstruction": 500
        }
    }
} 