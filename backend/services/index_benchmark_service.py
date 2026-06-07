"""
索引对比基准测试服务
对同一数据集使用不同的 Chroma HNSW 索引参数构建向量库，
测量构建时间、存储大小、检索延迟、召回率等指标，进行多维度对比分析。
"""
import os
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
import numpy as np

from services.embedding_service import EmbeddingService, EmbeddingConfig

logger = logging.getLogger(__name__)

# Chroma 存储路径
CHROMADB_PATH = "./03-vector-store/chromadb"

# ============================================================
# 8 种 Chroma HNSW 索引预设配置
# ============================================================
CHROMA_INDEX_PRESETS = {
    "cosine_default": {
        "name": "Cosine 默认参数（基线）",
        "description": "HNSW + Cosine 距离，M=16, ef_construction=100，作为对比基线",
        "metadata": {
            "hnsw:space": "cosine",
            "hnsw:M": 16,
            "hnsw:construction_ef": 100,
            "hnsw:search_ef": 10,
        }
    },
    "cosine_high_recall": {
        "name": "Cosine 高召回率",
        "description": "HNSW + Cosine，M=64, ef_construction=500，追求最高召回率",
        "metadata": {
            "hnsw:space": "cosine",
            "hnsw:M": 64,
            "hnsw:construction_ef": 500,
            "hnsw:search_ef": 100,
        }
    },
    "cosine_balanced": {
        "name": "Cosine 平衡型",
        "description": "HNSW + Cosine，M=32, ef_construction=200，速度与精度均衡",
        "metadata": {
            "hnsw:space": "cosine",
            "hnsw:M": 32,
            "hnsw:construction_ef": 200,
            "hnsw:search_ef": 50,
        }
    },
    "cosine_fast": {
        "name": "Cosine 快速构建/检索",
        "description": "HNSW + Cosine，M=8, ef_construction=50，最快速度",
        "metadata": {
            "hnsw:space": "cosine",
            "hnsw:M": 8,
            "hnsw:construction_ef": 50,
            "hnsw:search_ef": 5,
        }
    },
    "cosine_high_ef": {
        "name": "Cosine 高构建精度",
        "description": "HNSW + Cosine，M=16, ef_construction=500，提高构建时的搜索精度",
        "metadata": {
            "hnsw:space": "cosine",
            "hnsw:M": 16,
            "hnsw:construction_ef": 500,
            "hnsw:search_ef": 50,
        }
    },
    "cosine_high_m": {
        "name": "Cosine 高连接度",
        "description": "HNSW + Cosine，M=64, ef_construction=100，增加图连接密度",
        "metadata": {
            "hnsw:space": "cosine",
            "hnsw:M": 64,
            "hnsw:construction_ef": 100,
            "hnsw:search_ef": 50,
        }
    },
    "l2_default": {
        "name": "L2 距离基线",
        "description": "HNSW + L2 欧氏距离，M=16, ef_construction=100",
        "metadata": {
            "hnsw:space": "l2",
            "hnsw:M": 16,
            "hnsw:construction_ef": 100,
            "hnsw:search_ef": 10,
        }
    },
    "ip_default": {
        "name": "内积距离基线",
        "description": "HNSW + Inner Product 内积，M=16, ef_construction=100",
        "metadata": {
            "hnsw:space": "ip",
            "hnsw:M": 16,
            "hnsw:construction_ef": 100,
            "hnsw:search_ef": 10,
        }
    },
}


class IndexBenchmarkService:
    """
    索引对比基准测试服务

    对同一嵌入数据集，使用不同的 HNSW 参数构建 Chroma 向量库集合，
    并测量各项性能指标，生成对比分析报告。
    """

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.benchmark_results_dir = "07-benchmark-results"
        os.makedirs(self.benchmark_results_dir, exist_ok=True)
        os.makedirs(CHROMADB_PATH, exist_ok=True)

    # ---- 公共方法 ----

    def get_available_presets(self) -> Dict[str, Any]:
        """
        返回所有可用的索引预设配置，供前端展示。

        返回:
            dict: 预设名称 → 配置详情的映射
        """
        result = {}
        for key, preset in CHROMA_INDEX_PRESETS.items():
            result[key] = {
                "id": key,
                "name": preset["name"],
                "description": preset["description"],
                "metadata": preset["metadata"],
            }
        return result

    def run_benchmark(
        self,
        embedding_file: str,
        test_queries: List[str],
        presets: Optional[List[str]] = None,
        ground_truth: Optional[Dict[str, List[int]]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        运行索引对比基准测试。

        参数:
            embedding_file: 嵌入文件路径（02-embedded-docs 目录下的文件名）
            test_queries: 用于测试的查询列表
            presets: 要测试的预设名称列表，None 表示全部
            ground_truth: 每个查询对应的正确答案 chunk_id 列表，用于计算召回率
            top_k: 检索返回的最大结果数

        返回:
            包含所有对比结果的字典
        """
        if presets is None:
            presets = list(CHROMA_INDEX_PRESETS.keys())

        # 加载嵌入数据
        embedding_path = os.path.join("02-embedded-docs", embedding_file)
        if not os.path.exists(embedding_path):
            raise FileNotFoundError(f"Embedding file not found: {embedding_path}")

        embeddings_data = self._load_embeddings(embedding_path)
        base_name = embedding_file.replace(".json", "")

        logger.info(f"Starting benchmark with {len(presets)} presets, "
                     f"{len(embeddings_data['embeddings'])} vectors, "
                     f"{len(test_queries)} queries")

        benchmark_id = datetime.now().strftime("%Y%m%d%H%M%S")
        results = []

        for preset_key in presets:
            if preset_key not in CHROMA_INDEX_PRESETS:
                logger.warning(f"Unknown preset: {preset_key}, skipping")
                continue

            preset = CHROMA_INDEX_PRESETS[preset_key]
            logger.info(f"Benchmarking: {preset['name']} ({preset_key})")

            try:
                result = self._benchmark_single(
                    embeddings_data=embeddings_data,
                    base_name=base_name,
                    preset_key=preset_key,
                    preset=preset,
                    test_queries=test_queries,
                    ground_truth=ground_truth,
                    top_k=top_k,
                    benchmark_id=benchmark_id,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Benchmark failed for {preset_key}: {str(e)}")
                results.append({
                    "preset": preset_key,
                    "name": preset["name"],
                    "error": str(e),
                    "build_time_s": None,
                    "disk_size_mb": None,
                    "num_vectors": None,
                    "avg_query_latency_ms": None,
                    "p50_latency_ms": None,
                    "p99_latency_ms": None,
                    "recall_at_k": None,
                    "qps": None,
                })

        # 保存结果
        summary = {
            "benchmark_id": benchmark_id,
            "timestamp": datetime.now().isoformat(),
            "embedding_file": embedding_file,
            "num_vectors": len(embeddings_data["embeddings"]),
            "num_queries": len(test_queries),
            "top_k": top_k,
            "results": results,
        }

        filepath = self._save_results(summary, benchmark_id)
        summary["saved_filepath"] = filepath
        return summary

    def list_benchmark_results(self) -> List[Dict[str, Any]]:
        """列出所有历史基准测试结果"""
        results = []
        for filename in os.listdir(self.benchmark_results_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(self.benchmark_results_dir, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    results.append({
                        "id": filename.replace(".json", ""),
                        "timestamp": data.get("timestamp", ""),
                        "embedding_file": data.get("embedding_file", ""),
                        "num_presets": len(data.get("results", [])),
                        "num_queries": data.get("num_queries", 0),
                    })
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results

    def get_benchmark_result(self, benchmark_id: str) -> Dict[str, Any]:
        """获取特定基准测试结果详情"""
        file_path = os.path.join(self.benchmark_results_dir, f"{benchmark_id}.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Benchmark result not found: {benchmark_id}")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---- 私有方法 ----

    def _load_embeddings(self, file_path: str) -> Dict[str, Any]:
        """加载嵌入文件"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "embeddings" not in data:
            raise ValueError("Invalid embedding file: missing 'embeddings' key")
        return data

    def _benchmark_single(
        self,
        embeddings_data: Dict[str, Any],
        base_name: str,
        preset_key: str,
        preset: Dict[str, Any],
        test_queries: List[str],
        ground_truth: Optional[Dict[str, List[int]]],
        top_k: int,
        benchmark_id: str,
    ) -> Dict[str, Any]:
        """对单个索引预设执行完整基准测试"""

        # 1. 构建索引并计时
        build_start = time.time()
        collection_name = self._build_chroma_collection(
            embeddings_data=embeddings_data,
            base_name=base_name,
            preset_key=preset_key,
            preset=preset,
            benchmark_id=benchmark_id,
        )
        build_time = time.time() - build_start

        # 2. 获取集合引用
        client = chromadb.PersistentClient(CHROMADB_PATH)
        collection = client.get_collection(collection_name)

        # 3. 估算磁盘大小
        disk_size = self._estimate_collection_size(collection_name)

        # 4. 搜索基准测试
        search_metrics = self._benchmark_search(
            collection=collection,
            embeddings_data=embeddings_data,
            test_queries=test_queries,
            top_k=top_k,
        )

        # 5. 计算召回率（如果有标注数据）
        recall = None
        if ground_truth:
            recall = self._calculate_recall(
                collection=collection,
                embeddings_data=embeddings_data,
                test_queries=test_queries,
                ground_truth=ground_truth,
                top_k=top_k,
            )

        # 6. 清理测试集合
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

        return {
            "preset": preset_key,
            "name": preset["name"],
            "description": preset["description"],
            "hnsw_params": preset["metadata"],
            "build_time_s": round(build_time, 3),
            "disk_size_mb": round(disk_size, 2),
            "num_vectors": len(embeddings_data["embeddings"]),
            "avg_query_latency_ms": round(search_metrics["avg_latency_ms"], 2),
            "p50_latency_ms": round(search_metrics["p50_latency_ms"], 2),
            "p99_latency_ms": round(search_metrics["p99_latency_ms"], 2),
            "min_latency_ms": round(search_metrics["min_latency_ms"], 2),
            "max_latency_ms": round(search_metrics["max_latency_ms"], 2),
            "qps": round(search_metrics["qps"], 2),
            "recall_at_k": recall,
        }

    def _build_chroma_collection(
        self,
        embeddings_data: Dict[str, Any],
        base_name: str,
        preset_key: str,
        preset: Dict[str, Any],
        benchmark_id: str,
    ) -> str:
        """
        按指定参数构建 Chroma 向量集合。
        对每个文本块直接写入原始 embedding 向量。
        """
        collection_name = f"bench_{base_name[:30]}_{preset_key}_{benchmark_id}"
        # 清理名称
        collection_name = collection_name.replace("-", "_").replace(" ", "_")

        client = chromadb.PersistentClient(CHROMADB_PATH)

        # 获取 vector_dimension
        vector_dim = int(embeddings_data.get("vector_dimension", 0))
        if not vector_dim and embeddings_data["embeddings"]:
            vector_dim = len(embeddings_data["embeddings"][0].get("embedding", []))

        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

        # 创建集合时设置 HNSW 参数
        hnsw_metadata = dict(preset["metadata"])
        collection = client.create_collection(
            name=collection_name,
            metadata=hnsw_metadata,
        )

        # 批量写入向量
        batch_size = 100
        embeddings_list = embeddings_data["embeddings"]
        total = len(embeddings_list)

        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch = embeddings_list[start:end]

            ids = [f"chunk_{start + i}" for i in range(len(batch))]
            documents = [emb["metadata"].get("content", "")[:10000] for emb in batch]
            metadatas = [
                {
                    "chunk_id": emb["metadata"].get("chunk_id", 0),
                    "page_number": str(emb["metadata"].get("page_number", "")),
                    "word_count": emb["metadata"].get("word_count", 0),
                    "document_name": embeddings_data.get("filename", ""),
                }
                for emb in batch
            ]
            embeddings_vectors = [
                [float(x) for x in emb.get("embedding", [])] for emb in batch
            ]

            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings_vectors,
            )

        logger.info(f"Built collection '{collection_name}' with {total} vectors")
        return collection_name

    def _benchmark_search(
        self,
        collection: Any,
        embeddings_data: Dict[str, Any],
        test_queries: List[str],
        top_k: int,
    ) -> Dict[str, float]:
        """
        执行搜索基准测试，测量每次查询的延迟。
        对每个查询执行多次（预热 + 实际测量）取平均值。
        """
        embedding_provider = embeddings_data.get("embedding_provider", "huggingface")
        embedding_model = embeddings_data.get("embedding_model", "")
        config = EmbeddingConfig(provider=embedding_provider, model_name=embedding_model)

        latencies = []
        warmup_runs = 2
        measure_runs = 5

        for query in test_queries:
            # 生成查询向量（只做一次）
            query_embedding = self.embedding_service.create_single_embedding(
                query, provider=embedding_provider, model=embedding_model
            )

            # 预热
            for _ in range(warmup_runs):
                collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                )

            # 实际测量
            for _ in range(measure_runs):
                start = time.perf_counter()
                collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies.append(elapsed_ms)

        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)

        avg_latency = sum(latencies_sorted) / n
        p50_idx = int(n * 0.50)
        p99_idx = int(n * 0.99)

        return {
            "avg_latency_ms": avg_latency,
            "p50_latency_ms": latencies_sorted[min(p50_idx, n - 1)],
            "p99_latency_ms": latencies_sorted[min(p99_idx, n - 1)],
            "min_latency_ms": latencies_sorted[0],
            "max_latency_ms": latencies_sorted[-1],
            "qps": 1000.0 / avg_latency if avg_latency > 0 else 0,
            "total_measurements": n,
        }

    def _calculate_recall(
        self,
        collection: Any,
        embeddings_data: Dict[str, Any],
        test_queries: List[str],
        ground_truth: Dict[str, List[int]],
        top_k: int,
    ) -> Dict[str, float]:
        """
        计算 Recall@k。
        ground_truth 格式: {query_text: [relevant_chunk_ids]}
        """
        embedding_provider = embeddings_data.get("embedding_provider", "huggingface")
        embedding_model = embeddings_data.get("embedding_model", "")

        recall_scores = {k: [] for k in [1, 3, 5, 10] if k <= top_k or top_k >= k}
        if top_k not in recall_scores:
            recall_scores[top_k] = []

        for query in test_queries:
            gt_ids = set(ground_truth.get(query, []))
            if not gt_ids:
                continue

            query_embedding = self.embedding_service.create_single_embedding(
                query, provider=embedding_provider, model=embedding_model
            )

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )

            retrieved_ids = []
            if results.get("ids") and results["ids"][0]:
                retrieved_ids = [int(id_.replace("chunk_", "")) for id_ in results["ids"][0]]

            for k in recall_scores:
                hits = len(set(retrieved_ids[:k]) & gt_ids)
                recall = hits / len(gt_ids) if gt_ids else 0
                recall_scores[k].append(recall)

        return {
            f"recall@{k}": round(sum(scores) / len(scores), 4) if scores else 0
            for k, scores in recall_scores.items()
        }

    def _estimate_collection_size(self, collection_name: str) -> float:
        """估算集合的磁盘存储大小 (MB)"""
        collection_path = os.path.join(CHROMADB_PATH, collection_name)
        if not os.path.exists(collection_path):
            return 0.0

        total_size = 0
        for dirpath, _, filenames in os.walk(collection_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
        return total_size / (1024 * 1024)

    def _save_results(self, summary: Dict[str, Any], benchmark_id: str) -> str:
        """保存基准测试结果到 JSON 文件"""
        filepath = os.path.join(self.benchmark_results_dir, f"{benchmark_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"Benchmark results saved to: {filepath}")
        return filepath
