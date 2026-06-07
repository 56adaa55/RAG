"""
检索后优化服务（Post-retrieval Optimization）
对检索结果进行重排序、去重、多样性过滤和上下文压缩，
提升最终输入给 LLM 的上下文质量。
"""
import os
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI

logger = logging.getLogger(__name__)


class PostRetrievalOptimizer:
    """
    检索后优化器 — 对向量检索返回的结果进行后处理。

    五种策略：
    1. Cross-Encoder Rerank — 用 cross-encoder 模型精确重排序
    2. MMR Diversity — 最大边际相关性，平衡相关性与多样性
    3. Context Compression — 用 LLM 压缩提炼上下文
    4. Deduplication — 基于语义相似度去重
    5. LLM Relevance Filter — 用 LLM 过滤不相关内容
    """

    def __init__(self):
        self._cross_encoder = None
        self._cross_encoder_name = None
        self._llm_client = None
        self._llm_model = None

    # ================================================================
    # 策略 1: Cross-Encoder Rerank
    # ================================================================
    def rerank_cross_encoder(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ) -> List[Dict[str, Any]]:
        """
        使用 Cross-Encoder 模型对检索结果重新打分排序。
        Cross-Encoder 同时输入 query 和 document，比 Bi-Encoder 更精准。

        参数:
            query: 查询文本
            results: 检索结果列表，每项包含 "text" 字段
            top_k: 返回前 k 个结果，None 表示全部返回
            model_name: cross-encoder 模型名称

        返回:
            按新分数降序排列的结果列表，每项新增 "rerank_score" 字段
        """
        if not results:
            return results

        try:
            # 懒加载 cross-encoder
            if self._cross_encoder is None or self._cross_encoder_name != model_name:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading cross-encoder model: {model_name}")
                self._cross_encoder = CrossEncoder(model_name)
                self._cross_encoder_name = model_name

            # 构建 query-document 对
            pairs = [[query, result.get("text", "")[:2000]] for result in results]

            # 预测相关性分数
            scores = self._cross_encoder.predict(pairs, show_progress_bar=False)

            # 将分数附加到结果中
            reranked = []
            for result, score in zip(results, scores):
                reranked.append({
                    **result,
                    "rerank_score": float(score),
                    "original_score": result.get("score", 0),
                })

            # 按新分数降序排列
            reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

            if top_k:
                reranked = reranked[:top_k]

            logger.info(f"Cross-encoder reranked {len(results)} → {len(reranked)} results")
            return reranked

        except ImportError:
            logger.warning("sentence-transformers not installed, falling back to original order")
            return results
        except Exception as e:
            logger.error(f"Cross-encoder rerank failed: {str(e)}")
            return results

    # ================================================================
    # 策略 2: MMR Diversity
    # ================================================================
    def mmr_rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 5,
        lambda_param: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        MMR (Maximal Marginal Relevance) 多样性重排序。
        平衡结果的相关性（与查询相似）和多样性（与已选结果不重复）。

        参数:
            query: 查询文本
            results: 检索结果列表
            top_k: 返回的最大结果数
            lambda_param: 相关性权重 (0-1)，越大越偏重相关性，越小越偏重多样性

        返回:
            经过 MMR 挑选的结果列表
        """
        if len(results) <= 1:
            return results[:top_k]

        try:
            n = len(results)
            texts = [r.get("text", "") for r in results]

            # 用简单的词袋 TF 向量做相似度计算（不需要额外模型）
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            vectorizer = TfidfVectorizer(stop_words="english", max_features=500)
            # 包含 query 在内的所有文本
            all_texts = [query] + texts
            tfidf_matrix = vectorizer.fit_transform(all_texts)

            # 相似度矩阵：第一行是 query 与所有文档的相似度
            query_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
            doc_sim_matrix = cosine_similarity(tfidf_matrix[1:])

            # MMR 贪心选择
            selected_indices = []
            remaining = list(range(n))

            for _ in range(min(top_k, n)):
                if not remaining:
                    break

                mmr_scores = []
                for idx in remaining:
                    relevance = query_sim[idx]
                    diversity = 0.0
                    if selected_indices:
                        diversity = max(doc_sim_matrix[idx][s] for s in selected_indices)
                    mmr = lambda_param * relevance - (1 - lambda_param) * diversity
                    mmr_scores.append(mmr)

                best_local_idx = np.argmax(mmr_scores)
                best_idx = remaining[best_local_idx]
                selected_indices.append(best_idx)
                remaining.remove(best_idx)

            mmr_results = [results[i] for i in selected_indices]
            logger.info(f"MMR reranked {len(results)} → {len(mmr_results)} results (λ={lambda_param})")
            return mmr_results

        except ImportError:
            logger.warning("sklearn not available, falling back to original order")
            return results[:top_k]
        except Exception as e:
            logger.error(f"MMR rerank failed: {str(e)}")
            return results[:top_k]

    # ================================================================
    # 策略 3: Context Compression
    # ================================================================
    def compress_context(
        self,
        query: str,
        context_texts: List[str],
        max_length: int = 2000,
        provider: str = "deepseek",
        model: str = "deepseek-chat",
    ) -> str:
        """
        使用 LLM 将检索到的多段上下文压缩为精炼的摘要。
        去除冗余信息，保留与问题相关的关键内容。

        参数:
            query: 用户查询
            context_texts: 检索到的文本块列表
            max_length: 压缩后的最大字符数
            provider: LLM 提供商
            model: LLM 模型

        返回:
            压缩后的上下文字符串
        """
        if not context_texts:
            return ""

        raw_context = "\n\n---\n\n".join(
            f"[{i + 1}] {text}" for i, text in enumerate(context_texts)
        )

        # 如果上下文已经很短，不需要压缩
        if len(raw_context) <= max_length:
            return raw_context

        client, llm_model = self._get_llm(provider, model)
        if not client:
            logger.warning("No LLM available for context compression")
            # 简单截断
            return raw_context[:max_length]

        prompt = f"""请将以下检索到的文档上下文进行精炼压缩。保留与问题直接相关的关键信息和事实，
去除冗余重复的内容。压缩后的长度不超过 {max_length} 字符。

用户问题：{query}

原始上下文：
{raw_context[:4000]}

压缩后的上下文（保留关键事实和引用编号）："""

        try:
            response = client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,
            )
            compressed = response.choices[0].message.content.strip()
            logger.info(f"Context compressed from {len(raw_context)} → {len(compressed)} chars")
            return compressed
        except Exception as e:
            logger.error(f"Context compression failed: {str(e)}")
            return raw_context[:max_length]

    # ================================================================
    # 策略 4: Semantic Deduplication
    # ================================================================
    def deduplicate(
        self,
        results: List[Dict[str, Any]],
        threshold: float = 0.85,
    ) -> List[Dict[str, Any]]:
        """
        基于文本相似度去除重复/高度相似的内容块。

        参数:
            results: 检索结果列表
            threshold: 相似度阈值，超过此值视为重复

        返回:
            去重后的结果列表
        """
        if len(results) <= 1:
            return results

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            texts = [r.get("text", "") for r in results]
            vectorizer = TfidfVectorizer(stop_words="english", max_features=500)
            tfidf_matrix = vectorizer.fit_transform(texts)
            sim_matrix = cosine_similarity(tfidf_matrix)

            keep_indices = []
            dropped = []
            for i in range(len(results)):
                is_dup = False
                for j in keep_indices:
                    if sim_matrix[i][j] >= threshold:
                        is_dup = True
                        dropped.append(i)
                        break
                if not is_dup:
                    keep_indices.append(i)

            deduped = [results[i] for i in keep_indices]
            logger.info(f"Deduplication: kept {len(deduped)}, dropped {len(dropped)} (threshold={threshold})")
            return deduped

        except ImportError:
            logger.warning("sklearn not available for deduplication")
            return results
        except Exception as e:
            logger.error(f"Deduplication failed: {str(e)}")
            return results

    # ================================================================
    # 策略 5: LLM-based Relevance Filter
    # ================================================================
    async def filter_by_relevance(
        self,
        query: str,
        results: List[Dict[str, Any]],
        provider: str = "deepseek",
        model: str = "deepseek-chat",
    ) -> List[Dict[str, Any]]:
        """
        用 LLM 判断每个检索结果是否真的与问题相关。
        过滤掉不相关或仅表面匹配的内容块。

        参数:
            query: 查询文本
            results: 检索结果列表
            provider: LLM 提供商
            model: LLM 模型

        返回:
            被判定为相关的结果列表
        """
        if not results:
            return results

        client, llm_model = self._get_llm(provider, model)
        if not client:
            logger.warning("No LLM available for relevance filtering")
            return results

        # 构建评判 prompt
        docs_formatted = "\n\n".join(
            f"[DOC {i}]: {r.get('text', '')[:500]}"
            for i, r in enumerate(results)
        )

        prompt = f"""判断以下文档片段是否与用户问题相关。输出一个 JSON 数组，包含所有相关文档的编号。

用户问题：{query}

文档片段：
{docs_formatted}

请只输出 JSON 数组，如 [0, 2, 5]，不要其他内容："""

        try:
            response = client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
            )
            import json
            relevant_ids = json.loads(response.choices[0].message.content.strip())
            if isinstance(relevant_ids, list):
                filtered = [results[i] for i in relevant_ids if 0 <= i < len(results)]
                logger.info(f"Relevance filter: {len(results)} → {len(filtered)} relevant")
                return filtered
        except Exception as e:
            logger.error(f"Relevance filtering failed: {str(e)}")

        return results

    # ================================================================
    # 统一优化入口
    # ================================================================
    async def optimize(
        self,
        query: str,
        results: List[Dict[str, Any]],
        strategies: List[str],
        top_k: int = 5,
        provider: str = "deepseek",
        model: str = "deepseek-chat",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        按顺序执行指定的后优化策略。

        参数:
            query: 原始查询
            results: 原始检索结果
            strategies: 策略列表，如 ["deduplicate", "rerank", "filter"]
            top_k: 最终返回的最大结果数
            provider: LLM 提供商
            model: LLM 模型

        返回:
            {
                "original_count": int,
                "optimized_results": List[Dict],
                "optimized_count": int,
                "steps_applied": List[str],
            }
        """
        optimized = list(results)
        original_count = len(results)
        steps_applied = []

        for strategy in strategies:
            try:
                if strategy == "deduplicate":
                    threshold = kwargs.get("dedup_threshold", 0.85)
                    before = len(optimized)
                    optimized = self.deduplicate(optimized, threshold=threshold)
                    if len(optimized) < before:
                        steps_applied.append(f"deduplicate ({before}→{len(optimized)})")

                elif strategy == "rerank":
                    before = len(optimized)
                    optimized = self.rerank_cross_encoder(query, optimized, top_k=None)
                    steps_applied.append(f"cross-encoder rerank")

                elif strategy == "mmr":
                    lam = kwargs.get("mmr_lambda", 0.7)
                    optimized = self.mmr_rerank(query, optimized, top_k=top_k, lambda_param=lam)
                    steps_applied.append(f"mmr (λ={lam})")

                elif strategy == "filter":
                    before = len(optimized)
                    optimized = await self.filter_by_relevance(query, optimized, provider, model)
                    if len(optimized) < before:
                        steps_applied.append(f"relevance-filter ({before}→{len(optimized)})")

                elif strategy == "compress":
                    texts = [r.get("text", "") for r in optimized]
                    compressed = self.compress_context(
                        query, texts,
                        max_length=kwargs.get("max_context_length", 2000),
                        provider=provider, model=model,
                    )
                    # 压缩后返回的是单个字符串，但保持结果格式
                    optimized = [{"text": compressed, "score": 1.0, "metadata": {"compressed": True}}]
                    steps_applied.append("context-compression")

            except Exception as e:
                logger.error(f"Strategy '{strategy}' failed: {str(e)}")

        # 截取 top_k
        if top_k and len(optimized) > top_k:
            optimized = optimized[:top_k]

        return {
            "original_count": original_count,
            "optimized_results": optimized,
            "optimized_count": len(optimized),
            "steps_applied": steps_applied,
        }

    def _get_llm(self, provider: str = "deepseek", model: str = "deepseek-chat"):
        """懒加载 LLM 客户端"""
        if self._llm_client is None:
            if provider == "deepseek":
                api_key = os.getenv("DEEPSEEK_API_KEY")
                if api_key:
                    self._llm_client = OpenAI(
                        api_key=api_key,
                        base_url="https://api.deepseek.com"
                    )
                    self._llm_model = model if model else "deepseek-chat"
            elif provider == "aliyun":
                api_key = os.getenv("DASHSCOPE_API_KEY")
                if api_key:
                    self._llm_client = OpenAI(
                        api_key=api_key,
                        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    )
                    self._llm_model = model if model else "qwen-turbo"
        return self._llm_client, self._llm_model
