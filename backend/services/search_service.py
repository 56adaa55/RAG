from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from pymilvus import connections, Collection, utility
from services.embedding_service import EmbeddingService
from utils.config import VectorDBProvider, MILVUS_CONFIG
import os
import json
from pymilvus import MilvusClient, exceptions
import chromadb

chromadb_path = "./03-vector-store/chromadb"

logger = logging.getLogger(__name__)


class SearchService:
    """
    搜索服务类，负责向量数据库的连接和向量搜索功能
    提供集合列表查询、向量相似度搜索和搜索结果保存等功能
    """

    def __init__(self):
        """
        初始化搜索服务
        创建嵌入服务实例，设置Milvus连接URI，初始化搜索结果保存目录
        """
        self.embedding_service = EmbeddingService()
        self.milvus_uri = MILVUS_CONFIG["uri"]
        self.search_results_dir = "04-search-results"
        os.makedirs(self.search_results_dir, exist_ok=True)
        self.client=chromadb.PersistentClient(chromadb_path)

    def get_providers(self) -> List[Dict[str, str]]:
        """
        获取支持的向量数据库列表

        Returns:
            List[Dict[str, str]]: 支持的向量数据库提供商列表
        """
        return [
            {"id": VectorDBProvider.MILVUS.value, "name": "Milvus"},
            {"id": VectorDBProvider.CHROMA.value, "name": "Chroma"}
        ]

    def list_collections(self, provider: str = VectorDBProvider.CHROMA.value) -> List[Dict[str, Any]]:
        """
        获取指定向量数据库中的所有集合

        Args:
            provider (str): 向量数据库提供商，默认为Chroma

        Returns:
            List[Dict[str, Any]]: 集合信息列表，包含id、名称和实体数量

        Raises:
            Exception: 连接或查询集合时发生错误
        """
        try:
            logger.info(f"Listing collections for provider: {provider}")

            collections = []

            if provider == VectorDBProvider.MILVUS.value:
                try:
                    client = MilvusClient(
                        uri="http://localhost:19530",
                        token="root:Milvus",
                        db_name=self.milvus_uri
                    )
                    collection_names = client.list_collections()
                    logger.info(f"Milvus collections: {collection_names}")
                    for name in collection_names:
                        try:
                            stats = client.get_collection_stats(collection_name=name)
                            collections.append({
                                "id": name,
                                "name": name,
                                "count": stats.get("row_count", 0)
                            })
                        except Exception as e:
                            logger.error(f"Error getting info for Milvus collection {name}: {str(e)}")
                            collections.append({
                                "id": name,
                                "name": name,
                                "count": 0
                            })
                except Exception as e:
                    logger.error(f"Error connecting to Milvus: {str(e)}")
                    # Return empty list if Milvus is not available
                    return collections

            elif provider == VectorDBProvider.CHROMA.value:
                collection_names = self.client.list_collections()
                logger.info(f"Chroma collections: {collection_names}")

                for sample in collection_names:
                    name = sample.name
                    try:
                        collection = self.client.get_collection(name)
                        collections.append({
                            "id": name,
                            "name": name,
                            "count": collection.count()
                        })
                    except Exception as e:
                        logger.error(f"Error getting info for Chroma collection {name}: {str(e)}")

            return collections

        except Exception as e:
            logger.error(f"Error listing collections: {str(e)}")
            raise

    def save_search_results(self, query: str, collection_id: str, results: List[Dict[str, Any]]) -> str:
        """
        保存搜索结果到JSON文件

        Args:
            query (str): 搜索查询文本
            collection_id (str): 集合ID
            results (List[Dict[str, Any]]): 搜索结果列表

        Returns:
            str: 保存文件的路径

        Raises:
            Exception: 保存文件时发生错误
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            # 使用集合ID的基础名称（去掉路径相关字符）
            collection_base = os.path.basename(collection_id)
            filename = f"search_{collection_base}_{timestamp}.json"
            filepath = os.path.join(self.search_results_dir, filename)

            search_data = {
                "query": query,
                "collection_id": collection_id,
                "timestamp": datetime.now().isoformat(),
                "results": results
            }

            logger.info(f"Saving search results to: {filepath}")

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(search_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Successfully saved search results to: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error saving search results: {str(e)}")
            raise

    async def search(self,
                     query: str,
                     collection_id: str,
                     provider: str,
                     top_k: int = 3,
                     threshold: float = 0.7,
                     word_count_threshold: int = 20,
                     save_results: bool = False) -> Dict[str, Any]:
        """
        执行向量搜索

        Args:
            query (str): 搜索查询文本
            collection_id (str): 要搜索的集合ID
            provider (str): 向量数据库提供商 (milvus / chroma)
            top_k (int): 返回的最大结果数量，默认为3
            threshold (float): 相似度阈值，低于此值的结果将被过滤，默认为0.7
            word_count_threshold (int): 文本字数阈值，低于此值的结果将被过滤，默认为20
            save_results (bool): 是否保存搜索结果，默认为False

        Returns:
            Dict[str, Any]: 包含搜索结果的字典，如果保存结果则包含保存路径

        Raises:
            Exception: 搜索过程中发生错误
        """
        try:
            search_start = datetime.now()

            # 添加参数日志
            logger.info(f"Search parameters:")
            logger.info(f"- Provider: {provider}")
            logger.info(f"- Query: {query}")
            logger.info(f"- Collection ID: {collection_id}")
            logger.info(f"- Top K: {top_k}")
            logger.info(f"- Threshold: {threshold}")
            logger.info(f"- Word Count Threshold: {word_count_threshold}")
            logger.info(f"- Save Results: {save_results} (type: {type(save_results)})")

            # ============================================================
            # Chroma 搜索分支
            # ============================================================
            if provider == VectorDBProvider.CHROMA.value:
                logger.info(f"Loading Chroma collection: {collection_id}")

                collection = self.client.get_collection(collection_id)
                num_entities = collection.count()
                logger.info(f"Collection info - Entities: {num_entities}")

                # 获取样本实体以确定嵌入配置
                sample_entity = collection.query(
                    query_texts=[query],
                    n_results=1,
                )

                # 使用collection中存储的配置创建查询向量
                logger.info("Creating query embedding")
                query_embedding = self.embedding_service.create_single_embedding(
                    query,
                    provider=sample_entity['metadatas'][0][0].get('embedding_provider'),
                    model=sample_entity['metadatas'][0][0].get('embedding_model')
                )
                logger.info(f"Query embedding created with dimension: {len(query_embedding)}")

                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                )

                # 处理结果
                processed_results = []
                results_count = len(results['ids'][0])
                logger.info(f"Raw search results count: {results_count}")

                for hit in range(results_count):
                    hit_score = 1 - results['distances'][0][hit]
                    logger.info(f"Processing hit - Score: {hit_score}, Word Count: {results['metadatas'][0][hit].get('word_count')}")
                    if hit_score >= threshold:
                        processed_results.append({
                            "text": results.get('documents')[0][hit],
                            "score": float(hit_score),
                            "metadata": {
                                "source": results['metadatas'][0][hit].get('document_name'),
                                "page": results['metadatas'][0][hit].get('page_number'),
                                "chunk": results.get('ids')[0][hit],
                                "total_chunks": results['metadatas'][0][hit].get('total_chunks'),
                                "page_range": results['metadatas'][0][hit].get('page_range'),
                                "embedding_provider": results['metadatas'][0][hit].get('embedding_provider'),
                                "embedding_model": results['metadatas'][0][hit].get('embedding_model'),
                                "embedding_timestamp": results['metadatas'][0][hit].get('embedding_timestamp')
                            }
                        })

            # ============================================================
            # Milvus 搜索分支
            # ============================================================
            elif provider == VectorDBProvider.MILVUS.value:
                logger.info(f"Connecting to Milvus for collection: {collection_id}")

                client = MilvusClient(
                    uri="http://localhost:19530",
                    token="root:Milvus",
                    db_name=self.milvus_uri
                )

                # 获取样本实体以确定嵌入配置
                logger.info("Querying sample entity from Milvus")
                sample = client.query(
                    collection_name=collection_id,
                    filter="id >= 0",
                    output_fields=["embedding_provider", "embedding_model"],
                    limit=1
                )

                if not sample:
                    logger.error(f"Milvus collection {collection_id} is empty")
                    raise ValueError(f"Collection {collection_id} is empty")

                logger.info(f"Sample entity config: provider={sample[0].get('embedding_provider')}, model={sample[0].get('embedding_model')}")

                # 使用collection中存储的配置创建查询向量
                logger.info("Creating query embedding for Milvus search")
                query_embedding = self.embedding_service.create_single_embedding(
                    query,
                    provider=sample[0].get("embedding_provider"),
                    model=sample[0].get("embedding_model")
                )
                logger.info(f"Query embedding created with dimension: {len(query_embedding)}")

                # 执行Milvus搜索
                search_params = {
                    "metric_type": "COSINE",
                    "params": {"nprobe": 10}
                }
                logger.info(f"Executing Milvus search with params: {search_params}")

                search_results = client.search(
                    collection_name=collection_id,
                    data=[query_embedding],
                    anns_field="vector",
                    limit=top_k,
                    output_fields=[
                        "content",
                        "document_name",
                        "chunk_id",
                        "total_chunks",
                        "word_count",
                        "page_number",
                        "page_range",
                        "embedding_provider",
                        "embedding_model",
                        "embedding_timestamp"
                    ],
                    search_params=search_params
                )

                # 处理结果 — 与Chroma输出格式保持一致
                processed_results = []
                logger.info(f"Raw Milvus search results count: {len(search_results[0])}")

                for hits in search_results:
                    for hit in hits:
                        hit_score = hit.get("distance", 0)
                        logger.info(f"Processing hit - Score: {hit_score}, Word Count: {hit.get('entity', {}).get('word_count')}")
                        if hit_score >= threshold:
                            entity = hit.get("entity", {})
                            processed_results.append({
                                "text": entity.get("content", ""),
                                "score": float(hit_score),
                                "metadata": {
                                    "source": entity.get("document_name"),
                                    "page": entity.get("page_number"),
                                    "chunk": entity.get("chunk_id"),
                                    "total_chunks": entity.get("total_chunks"),
                                    "page_range": entity.get("page_range"),
                                    "embedding_provider": entity.get("embedding_provider"),
                                    "embedding_model": entity.get("embedding_model"),
                                    "embedding_timestamp": entity.get("embedding_timestamp")
                                }
                            })
            else:
                raise ValueError(f"Unsupported vector database provider: {provider}")

            # 计算搜索延迟
            search_end = datetime.now()
            search_latency_ms = (search_end - search_start).total_seconds() * 1000
            logger.info(f"Search completed in {search_latency_ms:.2f}ms")

            response_data = {
                "results": processed_results,
                "search_latency_ms": round(search_latency_ms, 2)
            }

            # 添加详细的保存逻辑日志
            logger.info(f"Preparing to handle save_results (flag: {save_results})")
            if save_results:
                logger.info("Save results is True, attempting to save...")
                if processed_results:
                    try:
                        filepath = self.save_search_results(query, collection_id, processed_results)
                        logger.info(f"Successfully saved results to: {filepath}")
                        response_data["saved_filepath"] = filepath
                    except Exception as e:
                        logger.error(f"Error saving results: {str(e)}")
                        response_data["save_error"] = str(e)
                        raise
                else:
                    logger.info("No results to save")
            else:
                logger.info("Save results is False, skipping save")

            return response_data

        except Exception as e:
            logger.error(f"Error performing search: {str(e)}")
            raise
        finally:
            connections.disconnect("default")