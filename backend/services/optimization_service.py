"""
优化服务模块：提供检索前和检索后优化功能

检索前优化（Pre-retrieval）：
  - 查询改写（Query Rewriting）：使用LLM将模糊查询改写为精确查询
  - 多查询扩展（Multi-Query Expansion）：生成多个查询变体用于多路召回
  - 关键词扩展（Keyword Expansion）：规则式关键词提取和扩展

检索后优化（Post-retrieval）：
  - Cross-Encoder重排序：使用sentence-transformers对检索结果重新打分
  - LLM重排序：使用LLM判断文档相关性并重新排序
  - MMR多样性重排序：最大边际相关性算法，平衡相关性与多样性
  - 上下文压缩：使用LLM提取和精炼最相关的内容片段
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
import numpy as np
from openai import OpenAI

logger = logging.getLogger(__name__)


class OptimizationService:
    """
    优化服务类：负责检索前和检索后的优化处理
    支持查询改写、多查询扩展、关键词扩展等检索前优化，
    以及Cross-Encoder重排序、LLM重排序、MMR多样性重排序、
    上下文压缩等检索后优化
    """

    def __init__(self):
        """初始化优化服务，设置API配置"""
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        self._cross_encoder = None

    # ========================================================================
    #  检索前优化方法 (Pre-retrieval Optimization)
    # ========================================================================

    def rewrite_query(
        self,
        query: str,
        provider: str = "deepseek",
        model: str = "deepseek-v3",
        api_key: Optional[str] = None
    ) -> str:
        """
        使用LLM改写查询，将模糊/口语化的查询改写为更精确的检索查询

        参数:
            query: 原始用户查询
            provider: LLM提供商 ("deepseek" 或 "aliyun")
            model: 模型名称
            api_key: API密钥（可选，默认从环境变量获取）

        返回:
            改写后的查询字符串
        """
        prompt = f"""你是一个查询优化专家。请将以下用户查询改写为更适合向量检索的精确查询。

改写规则：
1. 保留原始问题的核心意图和关键信息
2. 将口语化表达转换为正式、精确的表述
3. 补充必要的上下文和同义词，使查询更完整
4. 去除冗余和无关的修饰词
5. 如果是中文查询，保持中文输出；如果是英文查询，保持英文输出

原始查询：{query}

请直接输出改写后的查询，不要包含任何解释或额外内容。"""

        try:
            rewritten = self._call_llm(prompt, provider, model, api_key, max_tokens=256)
            logger.info(f"Query rewritten: '{query}' -> '{rewritten}'")
            return rewritten.strip()
        except Exception as e:
            logger.warning(f"Query rewriting failed: {e}, returning original query")
            return query

    def expand_query_multi(
        self,
        query: str,
        provider: str = "deepseek",
        model: str = "deepseek-v3",
        api_key: Optional[str] = None,
        num_variants: int = 3
    ) -> List[str]:
        """
        生成多个查询变体，用于多路召回融合

        参数:
            query: 原始用户查询
            provider: LLM提供商
            model: 模型名称
            api_key: API密钥
            num_variants: 生成的变体数量（默认3个）

        返回:
            查询变体列表（包含原始查询）
        """
        prompt = f"""你是一个查询扩展专家。请为以下用户查询生成{num_variants}个不同角度的查询变体。

要求：
1. 每个变体从不同角度表达相同的查询意图
2. 可以调整用词、句式、侧重点
3. 保持与原始查询相同的信息需求
4. 每个变体单独一行，以"- "开头
5. 如果是中文查询，保持中文输出

原始查询：{query}

请直接输出{num_variants}个查询变体："""

        try:
            response = self._call_llm(prompt, provider, model, api_key, max_tokens=512)
            variants = []
            for line in response.strip().split("\n"):
                line = line.strip()
                # 移除序号和前缀符号
                if line and (line.startswith("- ") or line.startswith("-")):
                    variant = line.lstrip("- ").strip()
                    if variant:
                        variants.append(variant)
                elif line and (line[0].isdigit() and (". " in line or "、" in line)):
                    # 处理 "1. xxx" 或 "1、xxx" 格式
                    import re
                    variant = re.sub(r'^\d+[.、．]\s*', '', line).strip()
                    if variant:
                        variants.append(variant)

            if not variants:
                logger.warning("Multi-query expansion returned no variants, using original query")
                return [query]

            # 始终包含原始查询
            if query not in variants:
                variants.insert(0, query)

            logger.info(f"Generated {len(variants)} query variants for: '{query}'")
            return variants[:num_variants + 1]  # 限制数量
        except Exception as e:
            logger.warning(f"Multi-query expansion failed: {e}, returning original query only")
            return [query]

    def expand_query_keywords(self, query: str) -> str:
        """
        规则式关键词提取和扩展（无需LLM）

        参数:
            query: 原始查询

        返回:
            扩展后的查询字符串（关键词拼接）
        """
        import re

        # 常见中英文停用词
        stopwords = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
            "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
            "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "can", "shall", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "through", "during",
            "before", "after", "above", "below", "between", "under", "again",
            "further", "then", "once", "here", "there", "when", "where", "why",
            "how", "all", "both", "each", "few", "more", "most", "other", "some",
            "such", "no", "nor", "not", "only", "own", "same", "so", "than",
            "too", "very", "just", "because", "but", "however", "if", "or",
            "and", "what", "which", "who", "whom", "this", "that", "these", "those",
        }

        # 提取中文词（2字及以上）
        chinese_words = re.findall(r'[一-鿿]{2,}', query)

        # 提取英文词（2字母及以上）
        english_words = re.findall(r'[a-zA-Z]{2,}', query)

        # 过滤停用词
        keywords = [w for w in chinese_words if w not in stopwords]
        keywords += [w for w in english_words if w.lower() not in stopwords]

        # 去重并拼接
        unique_keywords = list(dict.fromkeys(keywords))
        expanded = query + " " + " ".join(unique_keywords)

        logger.info(f"Keyword expansion: added {len(unique_keywords)} keywords")
        return expanded.strip()

    # ========================================================================
    #  检索后优化方法 (Post-retrieval Optimization)
    # ========================================================================

    def rerank_with_cross_encoder(
        self,
        query: str,
        results: List[Dict],
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ) -> List[Dict]:
        """
        使用Cross-Encoder模型对检索结果重新排序

        参数:
            query: 查询文本
            results: 检索结果列表，每项包含 "text" 字段
            model_name: Cross-Encoder模型名称

        返回:
            重新排序后的结果列表，每项增加了 "rerank_score" 字段
        """
        try:
            from sentence_transformers import CrossEncoder

            # 延迟加载模型
            if self._cross_encoder is None or self._cross_encoder.model_name != model_name:
                logger.info(f"Loading Cross-Encoder model: {model_name}")
                self._cross_encoder = CrossEncoder(model_name)
                self._cross_encoder.model_name = model_name

            if not results:
                return results

            # 构建(query, document)对
            pairs = [(query, result.get("text", "")) for result in results]

            # 计算相关性分数
            scores = self._cross_encoder.predict(pairs)

            # 将分数附加到结果中并排序
            for i, result in enumerate(results):
                result["rerank_score"] = float(scores[i])
                result["original_score"] = result.get("score", 0)

            # 按新分数降序排列
            reranked = sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)

            logger.info(
                f"Cross-Encoder reranked {len(results)} results. "
                f"Top score: {reranked[0].get('rerank_score', 0):.4f} "
                f"if results exist"
            )
            return reranked

        except ImportError:
            logger.warning("sentence-transformers not installed, falling back to LLM reranking")
            return self.rerank_with_llm(query, results)
        except Exception as e:
            logger.error(f"Cross-Encoder reranking failed: {e}")
            return results

    def rerank_with_llm(
        self,
        query: str,
        results: List[Dict],
        provider: str = "deepseek",
        model: str = "deepseek-v3",
        api_key: Optional[str] = None
    ) -> List[Dict]:
        """
        使用LLM对检索结果进行相关性打分和重排序

        参数:
            query: 查询文本
            results: 检索结果列表
            provider: LLM提供商
            model: 模型名称
            api_key: API密钥

        返回:
            重新排序后的结果列表
        """
        if not results:
            return results

        # 构建评分prompt
        documents_text = ""
        for i, result in enumerate(results):
            text = result.get("text", "")[:500]  # 截断长文本
            documents_text += f"[{i + 1}] {text}\n\n"

        prompt = f"""你是一个文档相关性评估专家。请评估以下文档与查询的相关性，并对每个文档打分（1-10分）。

查询：{query}

文档列表：
{documents_text}

请为每个文档给出相关性分数（1-10），分数越高表示越相关。输出格式：
[文档编号]: 分数 - 简短理由

请确保：
1. 严格按格式输出，每个文档一行
2. 分数为1-10的整数
3. 根据文档内容与查询的实际相关性打分"""

        try:
            response = self._call_llm(prompt, provider, model, api_key, max_tokens=512)
            scores = self._parse_llm_scores(response, len(results))

            # 将新分数附加到结果中
            for i, result in enumerate(results):
                if i < len(scores):
                    result["rerank_score"] = float(scores[i])
                    result["original_score"] = result.get("score", 0)
                else:
                    result["rerank_score"] = 0.0
                    result["original_score"] = result.get("score", 0)

            # 按新分数降序排列
            reranked = sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)

            logger.info(f"LLM reranked {len(results)} results")
            return reranked

        except Exception as e:
            logger.warning(f"LLM reranking failed: {e}, returning original order")
            return results

    def mmr_rerank(
        self,
        query: str,
        results: List[Dict],
        embedding_service=None,
        lambda_param: float = 0.7
    ) -> List[Dict]:
        """
        使用MMR (Maximal Marginal Relevance) 算法进行多样性重排序

        参数:
            query: 查询文本
            results: 检索结果列表
            embedding_service: 嵌入服务实例（用于获取文本向量）
            lambda_param: 相关性权重（0-1），越大越偏重相关性，越小越偏重多样性

        返回:
            多样性重排序后的结果列表
        """
        if not results or len(results) <= 1:
            return results

        try:
            # 获取查询向量
            if embedding_service:
                # 从第一个结果获取嵌入配置
                first_meta = results[0].get("metadata", {})
                emb_provider = first_meta.get("embedding_provider", "huggingface")
                emb_model = first_meta.get("embedding_model", "all-MiniLM-L6-v2")

                query_embedding = embedding_service.create_single_embedding(
                    query, provider=emb_provider, model=emb_model
                )
            else:
                # 无嵌入服务时，使用文本长度作为简单代理
                logger.warning("No embedding service available for MMR, using simple scoring")
                return self._simple_diversity_rerank(results)

            # 获取所有文档的嵌入向量（从结果中提取文本并重新嵌入）
            doc_texts = [r.get("text", "") for r in results]
            doc_embeddings = []
            for text in doc_texts:
                emb = embedding_service.create_single_embedding(
                    text, provider=emb_provider, model=emb_model
                )
                doc_embeddings.append(np.array(emb))

            query_emb = np.array(query_embedding)

            # 计算余弦相似度
            def cosine_sim(a, b):
                return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)

            # 计算每个文档与查询的相关性
            relevance_scores = [cosine_sim(query_emb, doc_emb) for doc_emb in doc_embeddings]

            # MMR贪心选择
            n = len(results)
            selected_indices = []
            remaining_indices = list(range(n))

            # 第一步：选择与查询最相关的文档
            first_idx = int(np.argmax(relevance_scores))
            selected_indices.append(first_idx)
            remaining_indices.remove(first_idx)

            # 迭代选择剩余文档
            while remaining_indices:
                mmr_scores = []
                for idx in remaining_indices:
                    # 相关性部分
                    relevance = relevance_scores[idx]
                    # 多样性部分（与已选文档的最大相似度）
                    max_sim_to_selected = max(
                        cosine_sim(doc_embeddings[idx], doc_embeddings[s])
                        for s in selected_indices
                    )
                    # MMR分数
                    mmr = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected
                    mmr_scores.append(mmr)

                # 选择MMR分数最高的文档
                best_local_idx = int(np.argmax(mmr_scores))
                best_idx = remaining_indices[best_local_idx]
                selected_indices.append(best_idx)
                remaining_indices.remove(best_idx)

            # 按MMR选择的顺序重新排列结果
            reranked = [results[i] for i in selected_indices]
            for i, result in enumerate(reranked):
                result["mmr_order"] = i + 1
                result["original_score"] = result.get("score", 0)
                result["diversity_score"] = float(relevance_scores[selected_indices[i]])

            logger.info(f"MMR reranked {len(results)} results (lambda={lambda_param})")
            return reranked

        except Exception as e:
            logger.error(f"MMR reranking failed: {e}, returning original order")
            return results

    def _simple_diversity_rerank(self, results: List[Dict]) -> List[Dict]:
        """简单的多样性重排序（基于文本Jaccard相似度去重）"""
        if len(results) <= 1:
            return results

        def jaccard_similarity(text1, text2):
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            return len(words1 & words2) / len(words1 | words2)

        selected = [results[0]]
        remaining = results[1:]

        while remaining:
            # 选择与已选文档最不相似的文档
            best_idx = 0
            best_diversity = -1
            for i, doc in enumerate(remaining):
                # 计算与已选文档的最大相似度（越小越好）
                max_sim = max(
                    jaccard_similarity(doc.get("text", ""), s.get("text", ""))
                    for s in selected
                )
                diversity = 1 - max_sim
                if diversity > best_diversity:
                    best_diversity = diversity
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        for i, result in enumerate(selected):
            result["diversity_order"] = i + 1

        return selected

    def compress_context(
        self,
        query: str,
        results: List[Dict],
        provider: str = "deepseek",
        model: str = "deepseek-v3",
        api_key: Optional[str] = None
    ) -> str:
        """
        使用LLM压缩和精炼检索到的上下文

        参数:
            query: 查询文本
            results: 检索结果列表
            provider: LLM提供商
            model: 模型名称
            api_key: API密钥

        返回:
            压缩后的上下文字符串
        """
        if not results:
            return ""

        # 拼接原始上下文
        context_parts = []
        total_chars = 0
        for i, result in enumerate(results):
            text = result.get("text", "")
            if total_chars + len(text) > 8000:  # 限制总长度
                text = text[:8000 - total_chars]
            context_parts.append(f"[文档{i + 1}] {text}")
            total_chars += len(text)
            if total_chars >= 8000:
                break

        raw_context = "\n\n".join(context_parts)

        prompt = f"""你是一个信息压缩专家。请从以下检索到的文档中，提取与查询最相关的关键信息。

查询：{query}

检索到的文档：
{raw_context}

请完成以下任务：
1. 提取所有与查询直接相关的关键事实和信息
2. 去除冗余、重复和不相关的内容
3. 将提取的信息组织成简洁、连贯的段落
4. 保留重要的事实细节、数据和引用来源
5. 如果某些文档完全不相关，可以忽略

请直接输出压缩后的上下文，不要包含任何解释。"""

        try:
            compressed = self._call_llm(prompt, provider, model, api_key, max_tokens=1024)
            logger.info(
                f"Context compressed from {len(raw_context)} chars "
                f"to {len(compressed)} chars"
            )
            return compressed.strip()
        except Exception as e:
            logger.warning(f"Context compression failed: {e}, returning raw context")
            return raw_context

    # ========================================================================
    #  统一入口方法 (Unified Entry Points)
    # ========================================================================

    def optimize_pre_retrieval(
        self,
        query: str,
        method: str = "rewrite",
        provider: str = "deepseek",
        model: str = "deepseek-v3",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        检索前优化的统一入口

        参数:
            query: 原始查询
            method: 优化方法 ("rewrite", "multi_query", "keywords")
            provider: LLM提供商（仅rewrite和multi_query需要）
            model: 模型名称
            api_key: API密钥

        返回:
            包含优化结果的字典：
            - method: 使用的方法
            - original_query: 原始查询
            - optimized_query: 优化后的查询（单字符串）
            - query_variants: 查询变体列表（仅multi_query方法）
        """
        logger.info(f"Pre-retrieval optimization: method={method}, query='{query}'")

        result = {
            "method": method,
            "original_query": query,
            "optimized_query": query,
        }

        if method == "rewrite":
            result["optimized_query"] = self.rewrite_query(
                query, provider, model, api_key
            )
        elif method == "multi_query":
            variants = self.expand_query_multi(
                query, provider, model, api_key
            )
            result["query_variants"] = variants
            result["optimized_query"] = " ".join(variants)  # 合并所有变体
        elif method == "keywords":
            result["optimized_query"] = self.expand_query_keywords(query)
        else:
            logger.warning(f"Unknown pre-retrieval method: {method}")

        return result

    def optimize_post_retrieval(
        self,
        query: str,
        results: List[Dict],
        method: str = "cross_encoder",
        provider: str = "deepseek",
        model: str = "deepseek-v3",
        api_key: Optional[str] = None,
        embedding_service=None,
        lambda_param: float = 0.7,
        compressed_context_only: bool = False
    ) -> Dict[str, Any]:
        """
        检索后优化的统一入口

        参数:
            query: 查询文本
            results: 检索结果列表
            method: 优化方法 ("cross_encoder", "llm_rerank", "mmr", "compress")
            provider: LLM提供商
            model: 模型名称
            api_key: API密钥
            embedding_service: 嵌入服务实例（MMR需要）
            lambda_param: MMR参数
            compressed_context_only: 是否只返回压缩后的上下文文本

        返回:
            包含优化结果的字典：
            - method: 使用的方法
            - optimized_results: 优化后的结果列表
            - compressed_context: 压缩后的上下文（仅compress方法）
            - original_count: 原始结果数
            - optimized_count: 优化后结果数
        """
        logger.info(f"Post-retrieval optimization: method={method}, results_count={len(results)}")

        result = {
            "method": method,
            "original_count": len(results),
            "optimized_results": results,
        }

        if method == "cross_encoder":
            result["optimized_results"] = self.rerank_with_cross_encoder(query, results)
        elif method == "llm_rerank":
            result["optimized_results"] = self.rerank_with_llm(
                query, results, provider, model, api_key
            )
        elif method == "mmr":
            result["optimized_results"] = self.mmr_rerank(
                query, results, embedding_service, lambda_param
            )
        elif method == "compress":
            compressed = self.compress_context(
                query, results, provider, model, api_key
            )
            result["compressed_context"] = compressed
            if compressed_context_only:
                # 返回压缩后的上下文作为单一结果
                result["optimized_results"] = [{
                    "text": compressed,
                    "score": 1.0,
                    "metadata": {"source": "compressed_context"}
                }]
        else:
            logger.warning(f"Unknown post-retrieval method: {method}")

        result["optimized_count"] = len(result["optimized_results"])
        return result

    # ========================================================================
    #  辅助方法 (Helper Methods)
    # ========================================================================

    def _call_llm(
        self,
        prompt: str,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        max_tokens: int = 512
    ) -> str:
        """
        调用LLM API的通用方法

        参数:
            prompt: 提示文本
            provider: 提供商 ("deepseek" 或 "aliyun")
            model: 模型名称
            api_key: API密钥
            max_tokens: 最大token数

        返回:
            LLM的响应文本
        """
        if provider == "deepseek":
            return self._call_deepseek(prompt, model, api_key, max_tokens)
        elif provider == "aliyun":
            return self._call_aliyun(prompt, model, api_key, max_tokens)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def _call_deepseek(
        self,
        prompt: str,
        model: str = "deepseek-v3",
        api_key: Optional[str] = None,
        max_tokens: int = 512
    ) -> str:
        """调用DeepSeek API"""
        key = api_key or self.deepseek_api_key
        if not key:
            raise ValueError("DeepSeek API key not provided")

        client = OpenAI(api_key=key, base_url="https://api.deepseek.com")

        model_id = "deepseek-chat" if model == "deepseek-v3" else "deepseek-reasoner"

        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "你是一个专业的查询优化和信息检索专家。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.3,
            stream=False
        )

        return response.choices[0].message.content.strip()

    def _call_aliyun(
        self,
        prompt: str,
        model: str = "qwen-turbo",
        api_key: Optional[str] = None,
        max_tokens: int = 512
    ) -> str:
        """调用阿里云DashScope API"""
        key = api_key or self.dashscope_api_key
        if not key:
            raise ValueError("DashScope API key not provided")

        client = OpenAI(
            api_key=key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的查询优化和信息检索专家。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.3,
            stream=False
        )

        return response.choices[0].message.content.strip()

    def _parse_llm_scores(self, response: str, expected_count: int) -> List[int]:
        """
        解析LLM返回的评分文本

        参数:
            response: LLM响应文本
            expected_count: 预期的文档数量

        返回:
            分数列表
        """
        import re
        scores = []
        lines = response.strip().split("\n")
        for line in lines:
            # 匹配 "[数字]: 分数" 或 "[数字] 分数" 或 "数字: 分数" 等格式
            match = re.search(r'\[?(\d+)\]?\s*[:：]\s*(\d+)', line)
            if match:
                scores.append(int(match.group(2)))
            else:
                # 尝试直接匹配分数
                match = re.search(r'(\d+)\s*分', line)
                if match:
                    scores.append(int(match.group(1)))

        # 如果解析失败，返回默认分数
        if not scores:
            logger.warning("Failed to parse LLM scores, using default scores")
            return list(range(expected_count, 0, -1))

        # 确保分数数量匹配
        while len(scores) < expected_count:
            scores.append(0)

        return scores[:expected_count]

    def get_available_methods(self) -> Dict[str, List[str]]:
        """
        获取可用的优化方法列表

        返回:
            包含检索前和检索后优化方法的字典
        """
        return {
            "pre_retrieval": ["rewrite", "multi_query", "keywords"],
            "post_retrieval": ["cross_encoder", "llm_rerank", "mmr", "compress"],
            "providers": ["deepseek", "aliyun"],
            "models": {
                "deepseek": ["deepseek-v3", "deepseek-r1"],
                "aliyun": ["qwen-turbo", "qwen3.6-plus"],
            }
        }
