"""
索引比较服务：支持对同一数据集使用不同索引方式进行批量对比
比较维度：索引构建时间、搜索延迟、召回率、索引大小
"""
import os
import json
import logging
import time
import asyncio
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from services.vector_store_service import VectorStoreService, VectorDBConfig
from services.embedding_service import EmbeddingService, EmbeddingConfig
from utils.config import INDEX_TYPES

logger = logging.getLogger(__name__)


class FlatIndex:
    """
    基于 numpy 的精确暴力搜索索引
    提供 100% 召回率的精确最近邻搜索，作为对比基线
    """

    def __init__(self, metric: str = "cosine"):
        self.metric = metric
        self.vectors: Optional[np.ndarray] = None
        self.documents: List[str] = []
        self.ids: List[str] = []
        self.dim: int = 0

    def add(self, ids: List[str], documents: List[str], embeddings: List[List[float]]):
        """添加向量到索引"""
        self.ids = list(ids)
        self.documents = list(documents)
        self.vectors = np.array(embeddings, dtype=np.float32)
        self.dim = self.vectors.shape[1]
        # L2 归一化（用于余弦相似度）
        if self.metric == "cosine":
            norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)  # 避免除零
            self.vectors = self.vectors / norms

    def search(self, query_vector: List[float], top_k: int = 5) -> Tuple[List[str], List[float], List[str]]:
        """
        精确搜索 top-k 最近邻

        返回:
            ids, distances, documents
        """
        if self.vectors is None:
            return [], [], []

        q = np.array(query_vector, dtype=np.float32).reshape(1, -1)

        if self.metric == "cosine":
            q = q / (np.linalg.norm(q) + 1e-10)
            # 归一化向量的内积 = 余弦相似度
            similarities = np.dot(self.vectors, q.T).flatten()
            # 取 top-k
            if len(similarities) <= top_k:
                top_indices = np.argsort(-similarities)
            else:
                top_indices = np.argpartition(-similarities, top_k)[:top_k]
                top_indices = top_indices[np.argsort(-similarities[top_indices])]
            scores = similarities[top_indices]

        elif self.metric == "l2":
            distances = np.linalg.norm(self.vectors - q, axis=1)
            if len(distances) <= top_k:
                top_indices = np.argsort(distances)
            else:
                top_indices = np.argpartition(distances, top_k)[:top_k]
                top_indices = top_indices[np.argsort(distances[top_indices])]
            # 转换为相似度分数（距离越小分数越高）
            max_dist = distances.max() if len(distances) > 0 else 1.0
            scores = 1.0 - distances[top_indices] / (max_dist + 1e-10)

        else:
            similarities = np.dot(self.vectors, q.T).flatten()
            if len(similarities) <= top_k:
                top_indices = np.argsort(-similarities)
            else:
                top_indices = np.argpartition(-similarities, top_k)[:top_k]
                top_indices = top_indices[np.argsort(-similarities[top_indices])]
            scores = similarities[top_indices]

        result_ids = [self.ids[i] for i in top_indices]
        result_docs = [self.documents[i] for i in top_indices]
        result_scores = [float(s) for s in scores]

        return result_ids, result_scores, result_docs

    @property
    def count(self) -> int:
        return len(self.ids)


class IndexComparisonService:
    """
    索引比较服务：批量使用不同索引方式建库并对比性能
    """

    def __init__(self):
        self.vector_store_service = VectorStoreService()
        self.embedding_service = EmbeddingService()
        self.comparison_dir = "03-vector-store/comparisons"
        os.makedirs(self.comparison_dir, exist_ok=True)
        # 使用 Chroma 客户端（与 vector_store_service 共享同一个持久化路径）
        self.chroma_client = self.vector_store_service.client

    def get_available_index_types(self, provider: str = "chroma") -> List[Dict[str, Any]]:
        """
        获取可用的索引类型列表
        """
        return self.vector_store_service.get_index_types(provider)

    def compare_index_modes(
        self,
        embedding_file: str,
        provider: str = "chroma",
        index_modes: Optional[List[str]] = None,
        test_queries: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        批量比较多种索引方式

        参数:
            embedding_file: 嵌入向量文件路径（相对于 02-embedded-docs）
            provider: 向量库名称
            index_modes: 要比较的索引模式列表，None 则比较所有
            test_queries: 用于测试的查询列表
            top_k: 检索返回数量

        返回:
            包含所有索引模式比较结果的字典
        """
        embedding_path = os.path.join("02-embedded-docs", embedding_file)
        if not os.path.exists(embedding_path):
            raise FileNotFoundError(f"Embedding file not found: {embedding_path}")

        # 确定要比较的索引模式
        if index_modes is None:
            all_types = INDEX_TYPES.get(provider, [])
            index_modes = [t.id for t in all_types]

        # 如果没有提供测试查询，从 embedding 数据中自动生成
        if test_queries is None:
            test_queries = self._generate_test_queries(embedding_path)

        # 预先生成所有测试查询的向量（只生成一次，避免重复计embedding时间）
        with open(embedding_path, "r", encoding="utf-8") as f:
            emb_data = json.load(f)
        emb_provider = emb_data.get("embedding_provider", "huggingface")
        emb_model = emb_data.get("embedding_model", "")
        logger.info(f"Pre-computing {len(test_queries)} query embeddings...")
        query_embeddings = []
        for q in test_queries:
            q_emb = self.embedding_service.create_single_embedding(q, provider=emb_provider, model=emb_model)
            query_embeddings.append(q_emb)
        logger.info(f"Query embeddings ready, starting comparison...")

        results = []
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        for mode in index_modes:
            logger.info(f"=== Comparing index mode: {mode} ===")
            try:
                result_entry = self._evaluate_single_mode(
                    embedding_path=embedding_path,
                    provider=provider,
                    index_mode=mode,
                    test_queries=test_queries,
                    top_k=top_k,
                    timestamp=timestamp,
                    query_embeddings=query_embeddings,
                )
                results.append(result_entry)
                logger.info(f"  Index time: {result_entry['index_time_sec']:.3f}s, "
                           f"Avg search: {result_entry['avg_search_time_ms']:.2f}ms")
            except Exception as e:
                logger.error(f"Error evaluating mode '{mode}': {str(e)}")
                results.append({
                    "index_mode": mode,
                    "index_mode_name": mode,
                    "status": "failed",
                    "error": str(e),
                })

        # 计算对比摘要
        successful = [r for r in results if r.get("status") == "success"]

        comparison_summary = {
            "provider": provider,
            "embedding_file": embedding_file,
            "test_queries": test_queries,
            "top_k": top_k,
            "timestamp": datetime.now().isoformat(),
            "total_modes_tested": len(index_modes),
            "successful_tests": len(successful),
            "results": results,
            "ranking": self._rank_index_modes(successful) if successful else {},
        }

        # 保存比较结果
        filepath = self._save_comparison_result(comparison_summary, timestamp)
        comparison_summary["saved_filepath"] = filepath

        return comparison_summary

    def _get_index_type_info(self, index_mode: str) -> Optional[Dict]:
        """获取索引类型的详细配置信息"""
        for provider_types in INDEX_TYPES.values():
            for t in provider_types:
                if t.id == index_mode:
                    return {"provider": t.provider, "params": dict(t.params), "name": t.name}
        return None

    def _evaluate_single_mode(
        self,
        embedding_path: str,
        provider: str,
        index_mode: str,
        test_queries: List[str],
        top_k: int,
        timestamp: str,
        query_embeddings: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """
        使用单一索引模式进行建库、搜索并记录指标

        参数:
            query_embeddings: 预先生成的查询向量列表（避免重复生成embedding）
        """
        # 检测索引类型信息
        type_info = self._get_index_type_info(index_mode)
        actual_provider = type_info["provider"] if type_info else provider
        mode_name = type_info["name"] if type_info else index_mode

        # --- 1. 加载 embedding 数据 ---
        with open(embedding_path, "r", encoding="utf-8") as f:
            emb_data = json.load(f)

        embeddings_list = emb_data.get("embeddings", [])
        doc_ids = [str(e["metadata"].get("chunk_id", i)) for i, e in enumerate(embeddings_list)]
        documents = [str(e["metadata"].get("content", "")) for e in embeddings_list]
        vectors = [[float(x) for x in e.get("embedding", [])] for e in embeddings_list]
        vector_dim = len(vectors[0]) if vectors else 0

        # --- 2. 索引构建（测量纯建索时间） ---
        index_start = time.time()
        collection_name = ""
        flat_index = None

        if actual_provider == "flat":
            # 使用 numpy Flat 索引
            metric = type_info["params"].get("metric", "cosine")
            flat_index = FlatIndex(metric=metric)
            flat_index.add(ids=doc_ids, documents=documents, embeddings=vectors)
            index_time = time.time() - index_start
            collection_name = f"flat_{metric}_{len(vectors)}vecs"
            total_vectors = len(vectors)
            index_size = len(vectors)
        else:
            # 使用 Chroma HNSW 索引
            config = VectorDBConfig(provider=provider, index_mode=index_mode)
            index_result = self.vector_store_service.index_embeddings(embedding_path, config)
            index_time = time.time() - index_start
            collection_name = index_result.get("collection_name", "")
            if not collection_name:
                raise RuntimeError("Indexing did not return a collection name")
            total_vectors = index_result.get("total_vectors", 0)
            index_size = index_result.get("index_size", "N/A")

        # --- 3. 搜索性能测试（只测量纯搜索时间，不含embedding生成） ---
        search_times = []
        all_search_results = []

        # 如果没有预先生成的查询向量，现场生成（兼容直接调用）
        if query_embeddings is None:
            emb_provider = emb_data.get("embedding_provider", "huggingface")
            emb_model = emb_data.get("embedding_model", "")
            query_embeddings = []
            for query in test_queries:
                q_emb = self.embedding_service.create_single_embedding(
                    query, provider=emb_provider, model=emb_model
                )
                query_embeddings.append(q_emb)

        for query_embedding in query_embeddings:
            search_start = time.time()
            try:
                if flat_index is not None:
                    # --- Flat 精确搜索 (numpy) ---
                    result_ids, result_scores, result_docs = flat_index.search(query_embedding, top_k)
                    formatted = [
                        {"id": rid, "text": doc, "score": score}
                        for rid, doc, score in zip(result_ids, result_docs, result_scores)
                    ]
                else:
                    # --- Chroma HNSW 近似搜索 ---
                    collection = self.chroma_client.get_collection(collection_name)
                    chroma_results = collection.query(
                        query_embeddings=[query_embedding],
                        n_results=top_k,
                    )
                    formatted = []
                    if chroma_results.get("ids") and chroma_results["ids"][0]:
                        for i, hit_id in enumerate(chroma_results["ids"][0]):
                            formatted.append({
                                "id": hit_id,
                                "text": chroma_results["documents"][0][i] if chroma_results.get("documents") else "",
                                "score": float(1 - chroma_results["distances"][0][i]) if chroma_results.get("distances") else 0,
                            })

                search_response = {"results": formatted}
            except Exception as e:
                logger.warning(f"Search failed: {e}")
                search_response = {"results": []}

            search_time = (time.time() - search_start) * 1000  # 转换为毫秒
            search_times.append(search_time)
            all_search_results.append(search_response.get("results", []))

        # --- 3. 计算指标 ---
        avg_search_time = sum(search_times) / len(search_times) if search_times else 0
        avg_results_count = (
            sum(len(r) for r in all_search_results) / len(all_search_results)
            if all_search_results
            else 0
        )

        # 清理：删除临时 collection（仅 Chroma）
        if flat_index is None:
            try:
                self.vector_store_service.delete_collection(provider, collection_name)
            except Exception as e:
                logger.warning(f"Could not delete comparison collection {collection_name}: {e}")

        return {
            "index_mode": index_mode,
            "index_mode_name": mode_name,
            "status": "success",
            "collection_name": collection_name,
            "total_vectors": total_vectors,
            "index_size": index_size,
            "index_time_sec": round(index_time, 3),
            "num_test_queries": len(test_queries),
            "avg_search_time_ms": round(avg_search_time, 2),
            "min_search_time_ms": round(min(search_times), 2) if search_times else 0,
            "max_search_time_ms": round(max(search_times), 2) if search_times else 0,
            "avg_results_count": round(avg_results_count, 1),
            "all_search_times_ms": [round(t, 2) for t in search_times],
        }

    def _generate_test_queries(self, embedding_path: str, num_queries: int = 5) -> List[str]:
        """
        从嵌入数据中自动生成测试查询（取前几个 chunk 的内容摘要作为查询）
        """
        try:
            with open(embedding_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            embeddings = data.get("embeddings", [])
            queries = []

            # 从文档的前、中、后段各取一些内容作为查询
            indices = []
            n = len(embeddings)
            if n > 0:
                # 前段
                indices.extend(range(0, min(2, n)))
                # 中段
                if n > 4:
                    indices.extend(range(n // 2, min(n // 2 + 2, n)))
                # 后段
                if n > 2:
                    indices.extend(range(max(n - 2, 0), n))

            for idx in indices[:num_queries]:
                content = embeddings[idx].get("metadata", {}).get("content", "")
                # 取前 100 个字符作为查询
                if content:
                    query = content[:150].strip()
                    if query:
                        queries.append(query)

            # 如果生成的查询不够，添加通用查询
            while len(queries) < num_queries:
                queries.append(f"test query {len(queries) + 1}")

            logger.info(f"Generated {len(queries)} test queries from embedding data")
            return queries[:num_queries]

        except Exception as e:
            logger.warning(f"Could not generate test queries: {e}")
            return ["machine learning", "deep neural networks", "data mining",
                    "natural language processing", "information retrieval"]

    def _get_mode_display_name(self, provider: str, mode_id: str) -> str:
        """获取索引模式的可读名称"""
        for t in INDEX_TYPES.get(provider, []):
            if t.id == mode_id:
                return t.name
        return mode_id

    def _rank_index_modes(self, results: List[Dict]) -> Dict[str, Any]:
        """
        对索引模式按综合性能排名
        """
        # 按搜索速度排名
        by_speed = sorted(results, key=lambda r: r.get("avg_search_time_ms", float("inf")))
        # 按建索速度排名
        by_index_speed = sorted(results, key=lambda r: r.get("index_time_sec", float("inf")))
        # 综合排名（搜索速度 + 建索速度各占 50%）
        if results:
            max_idx_time = max(r["index_time_sec"] for r in results) or 1
            max_search_time = max(r["avg_search_time_ms"] for r in results) or 1
            for r in results:
                idx_score = r["index_time_sec"] / max_idx_time
                search_score = r["avg_search_time_ms"] / max_search_time
                r["composite_score"] = round(0.5 * idx_score + 0.5 * search_score, 3)

            by_composite = sorted(results, key=lambda r: r.get("composite_score", float("inf")))

            return {
                "fastest_search": by_speed[0]["index_mode"] if by_speed else None,
                "fastest_indexing": by_index_speed[0]["index_mode"] if by_index_speed else None,
                "best_overall": by_composite[0]["index_mode"] if by_composite else None,
            }
        return {}

    def _save_comparison_result(self, data: Dict, timestamp: str) -> str:
        """保存比较结果到文件"""
        filename = f"index_comparison_{timestamp}.json"
        filepath = os.path.join(self.comparison_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Comparison result saved to {filepath}")
        return filepath

    def list_comparison_results(self) -> List[Dict[str, str]]:
        """列出历史比较结果"""
        if not os.path.exists(self.comparison_dir):
            return []
        files = []
        for filename in sorted(os.listdir(self.comparison_dir), reverse=True):
            if filename.endswith(".json"):
                filepath = os.path.join(self.comparison_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    files.append({
                        "id": filename,
                        "name": f"Comparison ({data.get('provider', '')}): {data.get('timestamp', '')}",
                        "timestamp": data.get("timestamp", ""),
                        "total_modes": data.get("total_modes_tested", 0),
                    })
                except Exception:
                    pass
        return files

    def get_comparison_result(self, file_id: str) -> Dict[str, Any]:
        """获取指定的比较结果详情"""
        filepath = os.path.join(self.comparison_dir, file_id)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Comparison result file not found: {file_id}")
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
