"""
索引对比分析服务

对同一个嵌入文件使用不同的 (向量库, 索引模式) 组合进行索引，
然后运行相同的查询集合，收集对比指标：
- 索引时间 (indexing_time_s)
- 索引大小 (index_size)
- 平均搜索延迟 (avg_search_latency_ms)
- 命中率 (avg_score_hit)
- 覆盖率 (avg_score_find)
"""

import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from services.vector_store_service import VectorStoreService, VectorDBConfig
from services.search_service import SearchService

logger = logging.getLogger(__name__)


class ComparisonService:
    """
    索引对比分析服务

    负责协调多组索引配置的批量索引、查询和指标采集。
    """

    def __init__(self):
        """初始化对比服务，创建向量存储和搜索服务实例"""
        self.vector_store = VectorStoreService()
        self.search_service = SearchService()

    async def run_comparison(
        self,
        embedding_file: str,
        index_configs: List[Dict[str, str]],
        queries: List[Dict[str, Any]],
        top_k: int = 10,
        threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        执行索引对比分析。

        对每一种 (provider, index_mode) 组合：
        1. 将嵌入文件索引到对应的向量库
        2. 对每条查询执行搜索
        3. 收集索引时间、搜索延迟、命中率等指标

        Args:
            embedding_file: 嵌入向量文件的完整路径
            index_configs: 索引配置列表，每项包含 provider 和 index_mode
                示例: [{"provider": "milvus", "index_mode": "flat"}, ...]
            queries: 查询列表，每项包含 query_text 和可选的 expected_pages
                示例: [{"query_text": "什么是机器学习？", "expected_pages": [1, 2]}, ...]
            top_k: 搜索返回的最大结果数
            threshold: 相似度阈值

        Returns:
            包含所有对比结果的字典，每项包含完整的指标数据
        """
        results = []
        total_configs = len(index_configs)

        for idx, config_spec in enumerate(index_configs):
            provider = config_spec.get("provider", "")
            index_mode = config_spec.get("index_mode", "")
            combination_label = f"{provider}_{index_mode}"

            logger.info(f"[{idx + 1}/{total_configs}] 开始对比: {combination_label}")

            # ----------------------------------------------------------
            # Step 1: 索引
            # ----------------------------------------------------------
            indexing_time_s = 0.0
            collection_name = ""
            index_size = "N/A"
            total_vectors = 0
            index_error = None

            try:
                config = VectorDBConfig(provider=provider, index_mode=index_mode)
                indexing_result = self.vector_store.index_embeddings(embedding_file, config)
                collection_name = indexing_result.get("collection_name", "")
                indexing_time_s = indexing_result.get("processing_time", 0.0)
                index_size = indexing_result.get("index_size", "N/A")
                total_vectors = indexing_result.get("total_vectors", 0)
                logger.info(f"[{combination_label}] 索引完成: collection={collection_name}, "
                            f"time={indexing_time_s:.2f}s, size={index_size}")
            except Exception as e:
                index_error = str(e)
                logger.error(f"[{combination_label}] 索引失败: {index_error}")
                # 索引失败的配置仍然记录，但标记错误
                results.append({
                    "provider": provider,
                    "index_mode": index_mode,
                    "combination": combination_label,
                    "collection_name": "",
                    "indexing_time_s": 0,
                    "index_size": "N/A",
                    "total_vectors": 0,
                    "avg_search_latency_ms": 0,
                    "avg_score_hit": None,
                    "avg_score_find": None,
                    "index_error": index_error,
                    "per_query_results": []
                })
                continue

            # ----------------------------------------------------------
            # Step 2: 逐条查询
            # ----------------------------------------------------------
            query_results = []
            total_search_latency_ms = 0.0
            total_score_hit = 0.0
            total_score_find = 0.0
            valid_queries = 0  # 有 expected_pages 的查询数

            for q_idx, q in enumerate(queries):
                query_text = q.get("query_text", "")
                expected_pages = q.get("expected_pages", [])

                if not query_text:
                    continue

                search_start = time.time()
                search_error = None
                found_pages = []
                search_hits = []

                try:
                    search_result = await self.search_service.search(
                        query=query_text,
                        collection_id=collection_name,
                        provider=provider,
                        top_k=top_k,
                        threshold=threshold
                    )
                    # 提取找到的页码
                    for r in search_result.get("results", []):
                        page = r.get("metadata", {}).get("page", None)
                        if page is not None:
                            found_pages.append(int(page))
                        search_hits.append({
                            "text": r.get("text", "")[:200],  # 截断文本用于展示
                            "score": r.get("score", 0),
                            "page": page
                        })
                except Exception as e:
                    search_error = str(e)
                    logger.warning(f"[{combination_label}] 查询 #{q_idx} 失败: {search_error}")

                search_latency_ms = (time.time() - search_start) * 1000
                total_search_latency_ms += search_latency_ms

                # 计算准确率指标（仅当提供了 expected_pages 时）
                score_hit = None
                score_find = None
                if expected_pages and found_pages:
                    hits = sum(1 for p in found_pages if p in expected_pages)
                    score_hit = hits / len(found_pages) if found_pages else 0.0
                    score_find = len(set(found_pages) & set(expected_pages)) / len(expected_pages)
                    total_score_hit += score_hit
                    total_score_find += score_find
                    valid_queries += 1

                query_results.append({
                    "query": query_text,
                    "found_pages": found_pages,
                    "expected_pages": expected_pages,
                    "score_hit": round(score_hit, 4) if score_hit is not None else None,
                    "score_find": round(score_find, 4) if score_find is not None else None,
                    "search_latency_ms": round(search_latency_ms, 2),
                    "search_error": search_error,
                    "hits": search_hits
                })

            # ----------------------------------------------------------
            # Step 3: 汇总该配置的指标
            # ----------------------------------------------------------
            total_queries_executed = len(query_results)
            avg_search_latency_ms = (
                round(total_search_latency_ms / total_queries_executed, 2)
                if total_queries_executed > 0 else 0.0
            )
            avg_score_hit = (
                round(total_score_hit / valid_queries, 4)
                if valid_queries > 0 else None
            )
            avg_score_find = (
                round(total_score_find / valid_queries, 4)
                if valid_queries > 0 else None
            )

            logger.info(
                f"[{combination_label}] 汇总: "
                f"avg_latency={avg_search_latency_ms}ms, "
                f"avg_score_hit={avg_score_hit}, "
                f"avg_score_find={avg_score_find}"
            )

            result_entry = {
                "provider": provider,
                "index_mode": index_mode,
                "combination": combination_label,
                "collection_name": collection_name,
                "indexing_time_s": round(indexing_time_s, 2),
                "index_size": index_size,
                "total_vectors": total_vectors,
                "avg_search_latency_ms": avg_search_latency_ms,
                "avg_score_hit": avg_score_hit,
                "avg_score_find": avg_score_find,
                "index_error": index_error,
                "total_queries_executed": total_queries_executed,
                "valid_queries": valid_queries,
                "per_query_results": query_results
            }
            results.append(result_entry)

        # 编译最终汇总
        return {
            "embedding_file": embedding_file,
            "total_configs": total_configs,
            "total_queries": len(queries),
            "top_k": top_k,
            "threshold": threshold,
            "timestamp": datetime.now().isoformat(),
            "results": results
        }
