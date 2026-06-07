"""
检索前优化服务（Pre-retrieval Optimization）
支持多种查询优化策略：Query Rewriting, Query Expansion, HyDE, Multi-Query Decomposition
"""
import os
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """
    查询优化器 — 在检索前对用户查询进行优化处理，
    提高检索的召回率和精准度。

    四种策略：
    1. Query Rewriting — 用 LLM 将模糊问题改写为精准检索查询
    2. Query Expansion — 基于关键词扩展，生成多个相关查询
    3. HyDE — 先生成假设性答案，用答案 embedding 做检索
    4. Multi-Query — 分解复杂问题为多个子查询，各自检索后融合
    """

    def __init__(self):
        # LLM 客户端（延迟初始化）
        self._llm_client = None
        self._llm_model = None
        self._generation_service = None

    def _get_llm(self, provider: str = "deepseek", model: str = "deepseek-chat"):
        """懒加载 LLM，优先复用 GenerationService 的配置"""
        if self._generation_service is None:
            from services.generation_service import GenerationService
            self._generation_service = GenerationService()

        if self._llm_client is None:
            if provider == "deepseek":
                api_key = os.getenv("DEEPSEEK_API_KEY")
                if api_key:
                    self._llm_client = OpenAI(
                        api_key=api_key,
                        base_url="https://api.deepseek.com"
                    )
                    model_map = {
                        "deepseek-chat": "deepseek-chat",
                        "deepseek-v3": "deepseek-chat",
                        "deepseek-r1": "deepseek-reasoner",
                    }
                    self._llm_model = model_map.get(model, "deepseek-chat")

            elif provider == "aliyun":
                api_key = os.getenv("DASHSCOPE_API_KEY")
                if api_key:
                    self._llm_client = OpenAI(
                        api_key=api_key,
                        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    )
                    self._llm_model = model
        return self._llm_client, self._llm_model

    # ================================================================
    # 策略 1: Query Rewriting — LLM 改写查询
    # ================================================================
    async def rewrite_query(
        self,
        query: str,
        provider: str = "deepseek",
        model: str = "deepseek-chat",
    ) -> str:
        """
        用 LLM 将用户的自然语言问题改写为更适合向量检索的关键词查询。

        参数:
            query: 原始用户查询
            provider: LLM 提供商
            model: LLM 模型

        返回:
            改写后的查询字符串
        """
        client, llm_model = self._get_llm(provider, model)
        if not client:
            logger.warning("No LLM available for query rewriting, returning original query")
            return query

        prompt = f"""你是一个专业的搜索查询优化助手。请将用户的自然语言问题改写为更适合搜索引擎和向量数据库检索的精简查询语句。

规则：
1. 保留原问题的核心语义和关键实体
2. 去除冗余的礼貌用语和修辞
3. 使用更标准化的术语
4. 只输出改写后的查询，不要加任何解释

原始问题：{query}

改写后的查询："""

        try:
            response = client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3,
            )
            rewritten = response.choices[0].message.content.strip()
            logger.info(f"Query rewritten: '{query}' → '{rewritten}'")
            return rewritten
        except Exception as e:
            logger.error(f"Query rewriting failed: {str(e)}")
            return query

    # ================================================================
    # 策略 2: Query Expansion — 关键词扩展
    # ================================================================
    async def expand_query(
        self,
        query: str,
        provider: str = "deepseek",
        model: str = "deepseek-chat",
        num_expansions: int = 3,
    ) -> List[str]:
        """
        生成查询的多个变体，从不同角度表达同一问题，提高召回率。

        参数:
            query: 原始查询
            provider: LLM 提供商
            model: LLM 模型
            num_expansions: 生成的变体数量

        返回:
            包含原始查询和扩展查询的列表
        """
        client, llm_model = self._get_llm(provider, model)
        if not client:
            logger.warning("No LLM available for query expansion")
            return [query]

        prompt = f"""将以下问题从不同角度重新表述，生成 {num_expansions} 个语义相同但表述不同的查询变体。
每条变体单独一行，不要编号，纯粹输出查询内容。

原始问题：{query}

{num_expansions} 个变体："""

        try:
            response = client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7,
            )
            expansions_text = response.choices[0].message.content.strip()
            expansions = [line.strip("- ").strip() for line in expansions_text.split("\n") if line.strip()]
            all_queries = [query] + expansions[:num_expansions]
            logger.info(f"Query expanded to {len(all_queries)} variants")
            return all_queries
        except Exception as e:
            logger.error(f"Query expansion failed: {str(e)}")
            return [query]

    # ================================================================
    # 策略 3: HyDE — 假设性文档嵌入
    # ================================================================
    async def hyde_generate(
        self,
        query: str,
        provider: str = "deepseek",
        model: str = "deepseek-chat",
    ) -> str:
        """
        HyDE (Hypothetical Document Embeddings):
        先生成一个假设性答案，然后用这个答案的 embedding 去检索。
        这利用了"答案和问题+上下文"在向量空间中更接近的特性。

        参数:
            query: 原始查询
            provider: LLM 提供商
            model: LLM 模型

        返回:
            生成的假设性答案文本（用于后续 embedding 和检索）
        """
        client, llm_model = self._get_llm(provider, model)
        if not client:
            logger.warning("No LLM available for HyDE, returning original query")
            return query

        prompt = f"""请根据以下问题，生成一段简要的假设性答案（100-200字）。这个答案不需要完全准确，
只是用来帮助搜索引擎找到相关文档。请直接输出答案内容。

问题：{query}

假设性答案："""

        try:
            response = client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.5,
            )
            hyde_answer = response.choices[0].message.content.strip()
            logger.info(f"HyDE generated answer ({len(hyde_answer)} chars)")
            return hyde_answer
        except Exception as e:
            logger.error(f"HyDE generation failed: {str(e)}")
            return query

    # ================================================================
    # 策略 4: Multi-Query Decomposition — 多查询分解
    # ================================================================
    async def decompose_query(
        self,
        query: str,
        provider: str = "deepseek",
        model: str = "deepseek-chat",
        max_subqueries: int = 3,
    ) -> List[str]:
        """
        将复杂问题拆解为多个子问题，分别检索后融合结果。
        适合需要综合多方面信息的复杂查询。

        参数:
            query: 原始复杂查询
            provider: LLM 提供商
            model: LLM 模型
            max_subqueries: 最大子问题数量

        返回:
            子查询列表
        """
        client, llm_model = self._get_llm(provider, model)
        if not client:
            logger.warning("No LLM available for query decomposition")
            return [query]

        prompt = f"""将以下复杂问题拆解为 {max_subqueries} 个以内独立的简单子问题。每个子问题单独一行，不要编号。
如果原问题本身很简单，就只输出原问题本身。

复杂问题：{query}

子问题："""

        try:
            response = client.chat.completions.create(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
            subqueries_text = response.choices[0].message.content.strip()
            subqueries = [line.strip("- ").strip() for line in subqueries_text.split("\n") if line.strip()]
            if not subqueries:
                subqueries = [query]
            logger.info(f"Query decomposed into {len(subqueries)} sub-queries")
            return subqueries
        except Exception as e:
            logger.error(f"Query decomposition failed: {str(e)}")
            return [query]

    # ================================================================
    # 统一入口
    # ================================================================
    async def optimize(
        self,
        query: str,
        strategies: List[str],
        provider: str = "deepseek",
        model: str = "deepseek-chat",
    ) -> Dict[str, Any]:
        """
        执行指定的优化策略，返回优化后的查询信息。

        参数:
            query: 原始查询
            strategies: 策略列表，如 ["rewrite", "expand", "hyde", "decompose"]
            provider: LLM 提供商
            model: LLM 模型

        返回:
            {
                "original_query": str,
                "strategy_results": {
                    "rewrite": str,
                    "expand": List[str],
                    "hyde": str,
                    "decompose": List[str],
                },
                "optimized_queries": List[str]  # 推荐用于检索的最终查询列表
            }
        """
        result = {
            "original_query": query,
            "strategy_results": {},
            "optimized_queries": [query],
        }

        if "rewrite" in strategies:
            rewritten = await self.rewrite_query(query, provider, model)
            result["strategy_results"]["rewrite"] = rewritten

        if "expand" in strategies:
            expanded = await self.expand_query(query, provider, model)
            result["strategy_results"]["expand"] = expanded
            # 扩展查询直接作为最终查询
            result["optimized_queries"] = expanded

        if "hyde" in strategies:
            hyde_answer = await self.hyde_generate(query, provider, model)
            result["strategy_results"]["hyde"] = hyde_answer

        if "decompose" in strategies:
            subqueries = await self.decompose_query(query, provider, model)
            result["strategy_results"]["decompose"] = subqueries
            result["optimized_queries"] = subqueries

        return result
