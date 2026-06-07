package com.example.demo.service;

import java.lang.*;
import com.alibaba.fastjson.JSON;
import com.example.demo.pojo.Answer;
import com.example.demo.pojo.Content;
import com.example.demo.pojo.Question;
import com.example.demo.utils.JsonParseUtil;
import org.elasticsearch.action.bulk.BulkRequest;
import org.elasticsearch.action.bulk.BulkResponse;
import org.elasticsearch.action.admin.indices.create.CreateIndexRequest;
import org.elasticsearch.action.admin.indices.create.CreateIndexResponse;
import org.elasticsearch.action.admin.indices.get.GetIndexRequest;
import org.elasticsearch.action.admin.indices.mapping.put.PutMappingRequest;
import org.elasticsearch.action.support.master.AcknowledgedResponse;
import org.elasticsearch.action.index.IndexRequest;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.common.unit.TimeValue;
import org.elasticsearch.common.xcontent.XContentType;
import org.elasticsearch.index.query.*;
import org.elasticsearch.index.query.functionscore.ScriptScoreQueryBuilder;
import org.elasticsearch.script.Script;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.elasticsearch.search.fetch.subphase.highlight.HighlightBuilder;
import org.elasticsearch.search.fetch.subphase.highlight.HighlightField;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.elasticsearch.client.RestHighLevelClient;

import java.io.IOException;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.example.demo.utils.HtmlParseUtil;



@Service
public class ContentService {

    // 将客户端注入
    @Autowired
    @Qualifier("restHighLevelClient")
    private RestHighLevelClient client;
    // ================= 定义全局索引名称变量 =================
    private static final String INDEX_QUESTION = "question2";
    private static final String INDEX_ANSWER = "answer2";
    private static final String FIELD_QUESTION_VECTOR = "question_vector_qwen_v3";
    private static final String FIELD_ANSWER_VECTOR = "answer_vector_qwen_v3";
    private static final int EMBEDDING_DIMENSION = 1024;
    private static final String DEFAULT_EMBEDDING_MODEL = "text-embedding-v3";
    private static final String DEFAULT_RERANK_MODEL = "qwen3-rerank";
    private static final String DASHSCOPE_EMBEDDING_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding";
    private static final String DASHSCOPE_RERANK_URL = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank";
    private static final int RERANK_CANDIDATE_LIMIT = 80;
    private static final int RRF_K = 60;
    private final Map<String, Map<String, Object>> aidQuestionCache = new ConcurrentHashMap<>();
    private volatile long aidQuestionCacheLoadedAt = 0L;
    private static final long AID_QUESTION_CACHE_TTL_MS = TimeUnit.MINUTES.toMillis(10);
    // ======================================================
    // 1、解析数据放到 es 中
    public boolean parseContent(String keyword) throws IOException {
        List<Content> contents = new HtmlParseUtil().parseJD(keyword);
        // 把查询的数据放入 es 中
        BulkRequest request = new BulkRequest();
        request.timeout("2m");

        for (int i = 0; i < contents.size(); i++) {
            request.add(
                    new IndexRequest("jd_goods")
                            .source(JSON.toJSONString(contents.get(i)), XContentType.JSON));

        }
        BulkResponse bulk = client.bulk(request, RequestOptions.DEFAULT);
        return !bulk.hasFailures();
    }

    // 2、获取这些数据实现基本的搜索功能
    public Map<String, Object> searchPage(String keyword, int pageNo, int pageSize, int sortRule) throws IOException {
        // keyword="机器学习";
        // keyword=keyword.getBytes("UTF-8").toString();
        System.out.println("【后端接收到请求】关键词: [" + keyword + "], 排序规则: " + sortRule);
        if (pageNo <= 1) {
            pageNo = 1;
        }
        if (pageSize <= 1) {
            pageSize = 1;
        }

        // 条件搜索
        // SearchRequest searchRequest = new SearchRequest("jd_goods");
        SearchRequest searchRequest = new SearchRequest("jddata");

        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();

        // 分页
        int offset = (pageNo - 1) * pageSize;
        sourceBuilder.from(offset).size(pageSize);
        sourceBuilder.trackTotalHits(true);
        // 精准匹配
        // TermQueryBuilder termQuery = QueryBuilders.termQuery("title", keyword);
        org.elasticsearch.index.query.MatchPhraseQueryBuilder matchQuery = QueryBuilders.matchPhraseQuery("title",
                keyword);
        // sourceBuilder.query(termQuery);
        sourceBuilder.query(matchQuery);

        // ========== 修改：基于 Painless 脚本的动态数值排序逻辑 ==========
        if (sortRule == 1 || sortRule == 2) {
            // 编写 Painless 脚本：
            // 1. 获取 price.keyword 的字符串值
            // 2. 替换掉里面可能含有的 '¥' 或 '￥' 等符号
            // 3. 将干净的字符串强转为 double 浮点数用于正确的数值排序
            String scriptText = "double price = 0.0; " +
                    "if (doc['price.keyword'].size() > 0) { " +
                    "   String p = doc['price.keyword'].value; " +
                    "   p = p.replace('¥', '').replace('￥', '').replace(',', '').trim(); " +
                    "   try { price = Double.parseDouble(p); } catch (Exception e) {} " +
                    "} " +
                    "return price;";

            // 构建脚本对象
            org.elasticsearch.script.Script script = new org.elasticsearch.script.Script(
                    org.elasticsearch.script.ScriptType.INLINE,
                    "painless",
                    scriptText,
                    java.util.Collections.emptyMap());

            // 构建脚本排序器 (告诉 ES 按照 NUMBER 数值类型来比较排序)
            org.elasticsearch.search.sort.ScriptSortBuilder scriptSortBuilder = org.elasticsearch.search.sort.SortBuilders
                    .scriptSort(script, org.elasticsearch.search.sort.ScriptSortBuilder.ScriptSortType.NUMBER);

            // 判断是升序还是降序
            if (sortRule == 1) {
                scriptSortBuilder.order(org.elasticsearch.search.sort.SortOrder.ASC);
            } else {
                scriptSortBuilder.order(org.elasticsearch.search.sort.SortOrder.DESC);
            }

            // 将排序器加入查询条件中
            sourceBuilder.sort(scriptSortBuilder);
        }
        // =========================================================

        sourceBuilder.timeout(new TimeValue(60, TimeUnit.SECONDS));
        // 执行搜索
        SearchRequest source = searchRequest.source(sourceBuilder);
        SearchResponse searchResponse = client.search(searchRequest, RequestOptions.DEFAULT);
        // 解析结果

        List<Map<String, Object>> list = new ArrayList<>();
        for (SearchHit documentFields : searchResponse.getHits().getHits()) {
            list.add(documentFields.getSourceAsMap());
        }
        long totalHits = searchResponse.getHits().getTotalHits().value;

        // 组装成 Map 返回
        Map<String, Object> resultMap = new HashMap<>();
        resultMap.put("list", list); // 当前页的商品数据
        resultMap.put("total", totalHits); // 搜到的总条数

        return resultMap;
    }

    public List<Map<String, Object>> searchQA(String keyword, int pageNo, int pageSize) throws IOException {
        // keyword="机器学习";
        // keyword=keyword.getBytes("UTF-8").toString();
        if (pageNo <= 1) {
            pageNo = 1;
        }
        if (pageSize <= 1) {
            pageSize = 1;
        }

        // 条件搜索
        SearchRequest searchRequest = new SearchRequest(INDEX_QUESTION);
        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();

        // 分页
        sourceBuilder.from((pageNo - 1) * pageSize).size(pageSize);

         // ====================================================================
        // 核心修改：使用 SimpleQueryStringQueryBuilder 支持多逻辑运算
        // ====================================================================
        /*
        * Simple Query String 支持的语法：
        * + 代表 AND (必须包含)
        * | 代表 OR (或者)
        * - 代表 NOT (排除)
        * " " 代表 短语精确匹配
        * ( ) 代表 优先级分组
        */
        SimpleQueryStringBuilder logicQueryBuilder = QueryBuilders.simpleQueryStringQuery(keyword)
                .field("qzh", 2.0f)    // 在中文标题中搜索，权重给 2 倍
                .field("qen", 1.0f)    // 在英文标题中搜索
                .field("qdomain", 1.0f)// 在领域中搜索
                .defaultOperator(Operator.OR); // 如果用户不敲符号，默认以空格作为 OR 关系

        // ====================================================================
        sourceBuilder.query(logicQueryBuilder);
        // 精准匹配 --- 不调整排序算法
        // TermQueryBuilder termQuery = QueryBuilders.termQuery("qzh", keyword);
        // sourceBuilder.query(termQuery);

        // MatchQueryBuilder matchQuery = QueryBuilders.matchQuery("qzh", keyword);
        // sourceBuilder.query(matchQuery);

        // 调整排序算法 ---boost
        // String[] keyword_buff = keyword.trim().split(" ");
        // if(keyword_buff.length<=1){
        // MatchQueryBuilder matchQuery = QueryBuilders.matchQuery("qzh", keyword);
        // sourceBuilder.query(matchQuery);
        // }
        // else{
        // MatchQueryBuilder matchQuery1 = QueryBuilders.matchQuery("qzh",
        // keyword_buff[0]);
        // matchQuery1.boost(2);
        //
        // String keyword_left=keyword_buff[1];
        // for(int i=2;i<keyword_buff.length;i++){
        // keyword_left=" "+keyword_buff[i];
        // }
        // MatchQueryBuilder matchQuery2 = QueryBuilders.matchQuery("qzh",
        // keyword_left);
        // BoolQueryBuilder boolQueryBuilder=QueryBuilders.boolQuery();
        // boolQueryBuilder.should(matchQuery1);
        // boolQueryBuilder.should(matchQuery2);
        // sourceBuilder.query(boolQueryBuilder);
        // }

        // 调整排序算法 ---boost positive and negative
        // String[] keyword_buff = keyword.trim().split(" ");
        // if(keyword_buff.length<=1){
        // MatchQueryBuilder matchQuery = QueryBuilders.matchQuery("qzh", keyword);
        // sourceBuilder.query(matchQuery);
        // }
        // else{
        // MatchQueryBuilder matchQuery1 = QueryBuilders.matchQuery("qzh",
        // keyword_buff[0]);
        // matchQuery1.boost(2);
        //
        // String keyword_left=keyword_buff[1];
        // for(int i=2;i<keyword_buff.length;i++){
        // keyword_left=" "+keyword_buff[i];
        // }
        // MatchQueryBuilder matchQuery2 = QueryBuilders.matchQuery("qzh",
        // keyword_left);
        // BoostingQueryBuilder
        // boosting=QueryBuilders.boostingQuery(matchQuery1,matchQuery2);
        // boosting.negativeBoost(0.2f);
        // sourceBuilder.query(boosting);
        // }

        // 调整排序算法 ---使用script score
        // String[] keyword_buff = keyword.trim().split(" ");
        // if (keyword_buff.length <= 1) {
        //     MatchQueryBuilder matchQuery = QueryBuilders.matchQuery("qzh", keyword);
        //     sourceBuilder.query(matchQuery);
        // } else {
        //     MatchQueryBuilder matchQuery1 = QueryBuilders.matchQuery("qzh", keyword_buff[0]);
        //     matchQuery1.boost(2);

        //     String keyword_left = keyword_buff[1];
        //     for (int i = 2; i < keyword_buff.length; i++) {
        //         keyword_left = " " + keyword_buff[i];
        //     }
        //     MatchQueryBuilder matchQuery2 = QueryBuilders.matchQuery("qzh", keyword_left);
        //     String scoreScript = "int weight=10;\n" +
        //             "def random= randomScore(params.uuidHash);\n" +
        //             "return weight*random";
        //     Map paraMap = new HashMap();
        //     int randint = (int) (Math.random() * 100);
        //     System.out.println(randint);
        //     paraMap.put("uuidHash", randint);
        //     Script script = new Script(Script.DEFAULT_SCRIPT_TYPE, "painless", scoreScript, paraMap);
        //     ScriptScoreQueryBuilder scriptScoreQueryBuilder = QueryBuilders.scriptScoreQuery(matchQuery2, script);
        //     BoolQueryBuilder boolQueryBuilder = QueryBuilders.boolQuery();
        //     boolQueryBuilder.should(matchQuery1);
        //     boolQueryBuilder.should(scriptScoreQueryBuilder);
        //     sourceBuilder.query(boolQueryBuilder);
        // }

        sourceBuilder.timeout(new TimeValue(60, TimeUnit.SECONDS));
        // 执行搜索
        SearchRequest source = searchRequest.source(sourceBuilder);
        SearchResponse searchResponse = client.search(searchRequest, RequestOptions.DEFAULT);
        // 解析结果

        List<Map<String, Object>> list = new ArrayList<>();
        for (SearchHit documentFields : searchResponse.getHits().getHits()) {
            list.add(documentFields.getSourceAsMap());
        }
        return list;
    }

    public List<Map<String, Object>> searchAllQA(String keyword, int pageNo, int pageSize) throws IOException {
        if (keyword == null) {
            keyword = "";
        }
        keyword = keyword.trim();
        if (pageNo <= 1) {
            pageNo = 1;
        }
        if (pageSize <= 1) {
            pageSize = 10;
        }

        int offset = (pageNo - 1) * pageSize;
        int fetchSize = Math.min(pageNo * pageSize, 500);

        List<Map<String, Object>> questionResults = searchQuestionCandidates(keyword, fetchSize);
        Map<String, Map<String, Object>> aidQuestionMap = getAidQuestionMetadata();
        List<Map<String, Object>> answerResults = searchAnswerCandidates(keyword, fetchSize, aidQuestionMap);

        normalizeCandidateScores(questionResults);
        normalizeCandidateScores(answerResults);

        for (Map<String, Object> item : questionResults) {
            double normalizedScore = (Double) item.getOrDefault("normalized_score", 0.0);
            double vectorScore = (Double) item.getOrDefault("normalized_vector_score", 0.0);
            String qzh = String.valueOf(item.getOrDefault("qzh", ""));
            String qdomain = String.valueOf(item.getOrDefault("qdomain", ""));
            double coverageBoost = keywordCoverageBoost(keyword, qzh + " " + qdomain);
            double semanticScore = semanticSimilarity(keyword, qzh + " " + qdomain);
            /* 
            问题结果的得分：
            normalizedScore：ES/BM25 原始分数归一化后的值。
            coverageBoost：query 中的关键词有多少出现在问题标题/领域里。
            semanticScore：query 和问题标题/领域之间的轻量语义重合度。
            */
            item.put("combined_score", normalizedScore * 0.45 + vectorScore * 0.30 + semanticScore * 0.15 + coverageBoost * 0.10);
            item.put("score", item.get("combined_score"));
        }

        Map<String, Double> questionScoreMap = buildQuestionScoreMap(questionResults);
        double maxCombinedQuestionScore = maxCombinedScore(questionResults);

        for (Map<String, Object> item : answerResults) {
            /*raw_score：用户 query 和问题文档之间的 ES 相关性分数 ，它主要由 ES 根据字段匹配情况算出来。*/
            double normalizedScore = (Double) item.getOrDefault("normalized_score", 0.0);
            double vectorScore = (Double) item.getOrDefault("normalized_vector_score", 0.0);
            String azh = String.valueOf(item.getOrDefault("azh", ""));
            String qzh = String.valueOf(item.getOrDefault("qzh", ""));
            String qdomain = String.valueOf(item.getOrDefault("qdomain", ""));
            String qid = String.valueOf(item.getOrDefault("qid", ""));
            /* coverageBoost：query 中的词有多少出现在答案正文和所属问题里。答案正文权重大，所属问题标题权重小*/
            /*当前问题的combined_score和最高的combined_score的比值，计算--line：318 */
            double parentQuestionScore = normalizeScore(questionScoreMap.getOrDefault(qid, 0.0), maxCombinedQuestionScore);
            /*
            semanticSimilarity：
            1. 清洗 query 和 text
            2. 去掉弱词
            3. 如果 text 直接包含 query 核心词，直接返回 1.0
            4. 否则把文本拆成 token
            5. 计算 query token 有多少出现在 text token 里
            示例：
            query: 什么是机器学习
            清洗后大致变成：机器学习
            然后拆成：
            机、器、学、习
            机器、器学、学习
            机器学、器学习
            如果答案中也包含这些片段，相似度就高。
            */
            double answerSemanticScore = semanticSimilarity(keyword, azh);
            double answerQuestionFit = semanticSimilarity(qzh, azh);
            double lengthQualityScore = answerLengthQualityScore(azh);
            double exactCoreBoost = exactCoreMatch(keyword, azh) ? 0.3 : 0.0;
            double qualityPenalty = answerQualityPenalty(azh);
            /*
            答案 combined_score =
            答案正文和 query 的 ES/BM25 匹配分 * 0.35
            + 答案所属问题和 query 的相关性 * 0.35
            + 答案正文和 query 的语义相似度 * 0.35
            + 所属问题标题/领域和 query 的语义相似度 * 0.2
            + 答案正文和所属问题的一致性 * 0.1      
            + 答案长度质量分 * 0.45
            + 关键词覆盖加分                         query 中的词有多少出现在答案正文和所属问题里。  
            + 核心词精确命中奖励                     query 中清洗后的词有多少出现在答案正文和所属问题里。  
            - 低质量答案惩罚                        扣掉一些明显质量差的答案
            */
            double qualityScore = lengthQualityScore * 0.75 + answerQuestionFit * 0.25;
            double combinedScore = normalizedScore * 0.35
                    + vectorScore * 0.30
                    + parentQuestionScore * 0.15
                    + answerSemanticScore * 0.10
                    + qualityScore * 0.10
                    + exactCoreBoost
                    - qualityPenalty;
            item.put("length_score", lengthQualityScore);
            item.put("vector_score", vectorScore);
            item.put("quality_score", qualityScore);
            item.put("combined_score", Math.max(0.0, combinedScore));
            item.put("score", item.get("combined_score"));
        }

        List<Map<String, Object>> combinedResults = mergeQuestionAndAnswerResults(questionResults, answerResults);
        applyQwenRerank(keyword, combinedResults);

        if (offset >= combinedResults.size()) {
            return new ArrayList<>();
        }
        return new ArrayList<>(combinedResults.subList(offset, Math.min(offset + pageSize, combinedResults.size())));
    }

    private List<Map<String, Object>> searchQuestionCandidates(String keyword, int fetchSize) throws IOException {
        List<Map<String, Object>> bm25Results = searchQuestionBm25Candidates(keyword, fetchSize);
        List<Map<String, Object>> vectorResults = searchQuestionVectorCandidates(keyword, fetchSize);
        return mergeRecallCandidates(bm25Results, vectorResults, "qid", fetchSize);
    }

    private List<Map<String, Object>> searchQuestionBm25Candidates(String keyword, int fetchSize) throws IOException {
        SearchRequest searchRequest = new SearchRequest(INDEX_QUESTION);
        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
        sourceBuilder.from(0).size(fetchSize);
        sourceBuilder.trackTotalHits(true);

        SimpleQueryStringBuilder questionQuery = QueryBuilders.simpleQueryStringQuery(keyword)
                .field("qzh", 4.0f)
                .field("qen", 1.0f)
                .field("qdomain", 1.5f)
                .defaultOperator(Operator.OR)
                .lenient(true);
        sourceBuilder.query(questionQuery);
        sourceBuilder.highlighter(new HighlightBuilder()
                .preTags("<em>")
                .postTags("</em>")
                .field(new HighlightBuilder.Field("qzh").fragmentSize(120).numOfFragments(1))
                .field(new HighlightBuilder.Field("qdomain").fragmentSize(80).numOfFragments(1))
                .encoder("html"));
        sourceBuilder.timeout(new TimeValue(60, TimeUnit.SECONDS));
        searchRequest.source(sourceBuilder);

        SearchResponse searchResponse = client.search(searchRequest, RequestOptions.DEFAULT);
        List<Map<String, Object>> results = new ArrayList<>();
        for (SearchHit hit : searchResponse.getHits().getHits()) {
            Map<String, Object> source = new HashMap<>(hit.getSourceAsMap());
            String qzh = String.valueOf(source.getOrDefault("qzh", ""));
            String qdomain = String.valueOf(source.getOrDefault("qdomain", ""));
            source.put("resultType", "question");
            source.put("title", qzh);
            source.put("titleHtml", highlightOrEscaped(hit, "qzh", qzh, 120));
            source.put("snippet", qdomain);
            source.put("snippetHtml", highlightOrEscaped(hit, "qdomain", qdomain, 80));
            source.put("raw_score", (double) hit.getScore());
            results.add(source);
        }
        return results;
    }

    private List<Map<String, Object>> searchAnswerCandidates(String keyword, int fetchSize,
            Map<String, Map<String, Object>> aidQuestionMap) throws IOException {
        List<Map<String, Object>> bm25Results = searchAnswerBm25Candidates(keyword, fetchSize, aidQuestionMap);
        List<Map<String, Object>> vectorResults = searchAnswerVectorCandidates(keyword, fetchSize, aidQuestionMap);
        return mergeRecallCandidates(bm25Results, vectorResults, "aid", fetchSize);
    }

    private List<Map<String, Object>> searchAnswerBm25Candidates(String keyword, int fetchSize,
            Map<String, Map<String, Object>> aidQuestionMap) throws IOException {
        SearchRequest searchRequest = new SearchRequest(INDEX_ANSWER);
        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
        sourceBuilder.from(0).size(fetchSize);
        sourceBuilder.trackTotalHits(true);

        SimpleQueryStringBuilder answerQuery = QueryBuilders.simpleQueryStringQuery(keyword)
                .field("azh", 4.0f)
                .field("aen", 1.0f)
                .defaultOperator(Operator.OR)
                .lenient(true);
        sourceBuilder.query(answerQuery);
        sourceBuilder.highlighter(new HighlightBuilder()
                .preTags("<em>")
                .postTags("</em>")
                .field(new HighlightBuilder.Field("azh").fragmentSize(180).numOfFragments(1))
                .encoder("html"));
        sourceBuilder.timeout(new TimeValue(60, TimeUnit.SECONDS));
        searchRequest.source(sourceBuilder);

        SearchResponse searchResponse = client.search(searchRequest, RequestOptions.DEFAULT);
        List<Map<String, Object>> results = new ArrayList<>();
        for (SearchHit hit : searchResponse.getHits().getHits()) {
            Map<String, Object> answerData = new HashMap<>(hit.getSourceAsMap());
            String aid = String.valueOf(answerData.getOrDefault("aid", ""));
            Map<String, Object> questionMeta = aidQuestionMap.get(aid);
            if (questionMeta != null) {
                answerData.putIfAbsent("qid", questionMeta.get("qid"));
                answerData.putIfAbsent("qzh", questionMeta.get("qzh"));
                answerData.putIfAbsent("qdomain", questionMeta.get("qdomain"));
            }

            String qzh = String.valueOf(answerData.getOrDefault("qzh", "答案 " + aid));
            String azh = String.valueOf(answerData.getOrDefault("azh", ""));
            answerData.put("resultType", "answer");
            answerData.put("title", qzh);
            answerData.put("titleHtml", escapeHtml(shorten(qzh, 120)));
            answerData.put("snippet", shorten(azh, 180));
            answerData.put("snippetHtml", highlightOrEscaped(hit, "azh", azh, 180));
            answerData.put("raw_score", (double) hit.getScore());
            results.add(answerData);
        }
        return results;
    }

    private List<Map<String, Object>> searchQuestionVectorCandidates(String keyword, int fetchSize) {
        List<Map<String, Object>> results = new ArrayList<>();
        if (keyword == null || keyword.trim().isEmpty()) {
            return results;
        }
        try {
            SearchResponse searchResponse = searchByVector(INDEX_QUESTION, FIELD_QUESTION_VECTOR, keyword, fetchSize);
            for (SearchHit hit : searchResponse.getHits().getHits()) {
                Map<String, Object> source = new HashMap<>(hit.getSourceAsMap());
                String qzh = String.valueOf(source.getOrDefault("qzh", ""));
                String qdomain = String.valueOf(source.getOrDefault("qdomain", ""));
                source.put("resultType", "question");
                source.put("title", qzh);
                source.put("titleHtml", escapeHtml(shorten(qzh, 120)));
                source.put("snippet", qdomain);
                source.put("snippetHtml", escapeHtml(shorten(qdomain, 80)));
                source.put("vector_raw_score", Math.max(0.0, (double) hit.getScore()));
                results.add(source);
            }
        } catch (Exception e) {
            System.out.println("Vector question recall skipped: " + e.getMessage());
        }
        return results;
    }

    private List<Map<String, Object>> searchAnswerVectorCandidates(String keyword, int fetchSize,
            Map<String, Map<String, Object>> aidQuestionMap) {
        List<Map<String, Object>> results = new ArrayList<>();
        if (keyword == null || keyword.trim().isEmpty()) {
            return results;
        }
        try {
            SearchResponse searchResponse = searchByVector(INDEX_ANSWER, FIELD_ANSWER_VECTOR, keyword, fetchSize);
            for (SearchHit hit : searchResponse.getHits().getHits()) {
                Map<String, Object> answerData = new HashMap<>(hit.getSourceAsMap());
                String aid = String.valueOf(answerData.getOrDefault("aid", ""));
                attachQuestionMetadata(answerData, aidQuestionMap.get(aid));
                String qzh = String.valueOf(answerData.getOrDefault("qzh", "绛旀 " + aid));
                String azh = String.valueOf(answerData.getOrDefault("azh", ""));
                answerData.put("resultType", "answer");
                answerData.put("title", qzh);
                answerData.put("titleHtml", escapeHtml(shorten(qzh, 120)));
                answerData.put("snippet", shorten(azh, 180));
                answerData.put("snippetHtml", escapeHtml(shorten(azh, 180)));
                answerData.put("vector_raw_score", Math.max(0.0, (double) hit.getScore()));
                results.add(answerData);
            }
        } catch (Exception e) {
            System.out.println("Vector answer recall skipped: " + e.getMessage());
        }
        return results;
    }

    private SearchResponse searchByVector(String indexName, String vectorField, String keyword, int fetchSize)
            throws IOException {
        SearchRequest searchRequest = new SearchRequest(indexName);
        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
        sourceBuilder.from(0).size(fetchSize);
        sourceBuilder.trackTotalHits(true);
        Map<String, Object> params = new HashMap<>();
        params.put("query_vector", toFloatList(createEmbedding(keyword, "query")));
        String scriptCode = "cosineSimilarity(params.query_vector, '" + vectorField + "') + 1.0";
        Script script = new Script(Script.DEFAULT_SCRIPT_TYPE, "painless", scriptCode, params);
        sourceBuilder.query(QueryBuilders.scriptScoreQuery(QueryBuilders.matchAllQuery(), script));
        sourceBuilder.timeout(new TimeValue(60, TimeUnit.SECONDS));
        searchRequest.source(sourceBuilder);
        return client.search(searchRequest, RequestOptions.DEFAULT);
    }

    private List<Map<String, Object>> mergeRecallCandidates(List<Map<String, Object>> bm25Results,
            List<Map<String, Object>> vectorResults, String idField, int fetchSize) {
        Map<String, Map<String, Object>> merged = new LinkedHashMap<>();
        addRecallResults(merged, bm25Results, idField, "bm25_rank_score", "raw_score");
        addRecallResults(merged, vectorResults, idField, "vector_rank_score", "vector_raw_score");
        List<Map<String, Object>> results = new ArrayList<>(merged.values());
        for (Map<String, Object> item : results) {
            double bm25RankScore = (Double) item.getOrDefault("bm25_rank_score", 0.0);
            double vectorRankScore = (Double) item.getOrDefault("vector_rank_score", 0.0);
            double bm25Score = (Double) item.getOrDefault("raw_score", 0.0);
            double vectorScore = (Double) item.getOrDefault("vector_raw_score", 0.0);
            item.put("retrieval_score", bm25RankScore + vectorRankScore);
            item.put("raw_score", bm25Score);
            item.put("vector_raw_score", vectorScore);
        }
        results.sort((a, b) -> Double.compare(
                (Double) b.getOrDefault("retrieval_score", 0.0),
                (Double) a.getOrDefault("retrieval_score", 0.0)));
        if (results.size() > fetchSize) {
            return new ArrayList<>(results.subList(0, fetchSize));
        }
        return results;
    }

    private void addRecallResults(Map<String, Map<String, Object>> merged, List<Map<String, Object>> results,
            String idField, String rankScoreField, String rawScoreField) {
        for (int i = 0; i < results.size(); i++) {
            Map<String, Object> item = results.get(i);
            String id = String.valueOf(item.getOrDefault(idField, ""));
            if (id.isEmpty()) {
                id = String.valueOf(item.getOrDefault("title", "")) + "#" + i;
            }
            Map<String, Object> target = merged.get(id);
            if (target == null) {
                target = new HashMap<>(item);
                merged.put(id, target);
            }
            double rankScore = 1.0 / (RRF_K + i + 1.0);
            target.put(rankScoreField, Math.max((Double) target.getOrDefault(rankScoreField, 0.0), rankScore));
            target.put(rawScoreField, Math.max((Double) target.getOrDefault(rawScoreField, 0.0),
                    (Double) item.getOrDefault(rawScoreField, 0.0)));
        }
    }

    private void normalizeCandidateScores(List<Map<String, Object>> results) {
        double maxBm25 = 0.0;
        double maxVector = 0.0;
        double maxRetrieval = 0.0;
        for (Map<String, Object> item : results) {
            maxBm25 = Math.max(maxBm25, (Double) item.getOrDefault("raw_score", 0.0));
            maxVector = Math.max(maxVector, (Double) item.getOrDefault("vector_raw_score", 0.0));
            maxRetrieval = Math.max(maxRetrieval, (Double) item.getOrDefault("retrieval_score", 0.0));
        }
        for (Map<String, Object> item : results) {
            item.put("normalized_bm25_score", normalizeScore((Double) item.getOrDefault("raw_score", 0.0), maxBm25));
            item.put("normalized_vector_score", normalizeScore((Double) item.getOrDefault("vector_raw_score", 0.0), maxVector));
            item.put("normalized_score", normalizeScore((Double) item.getOrDefault("retrieval_score", 0.0), maxRetrieval));
        }
    }

    private List<Map<String, Object>> mergeQuestionAndAnswerResults(List<Map<String, Object>> questionResults,
            List<Map<String, Object>> answerResults) {
        normalizeCombinedScores(questionResults);
        normalizeCombinedScores(answerResults);
        List<Map<String, Object>> merged = new ArrayList<>();
        addTypedResultsWithRrf(merged, questionResults);
        addTypedResultsWithRrf(merged, answerResults);
        merged.sort((a, b) -> Double.compare(
                (Double) b.getOrDefault("final_score", 0.0),
                (Double) a.getOrDefault("final_score", 0.0)));
        return merged;
    }

    private void normalizeCombinedScores(List<Map<String, Object>> results) {
        double maxScore = maxCombinedScore(results);
        results.sort((a, b) -> Double.compare(
                (Double) b.getOrDefault("combined_score", 0.0),
                (Double) a.getOrDefault("combined_score", 0.0)));
        for (int i = 0; i < results.size(); i++) {
            Map<String, Object> item = results.get(i);
            double normalized = normalizeScore((Double) item.getOrDefault("combined_score", 0.0), maxScore);
            double rrfScore = 1.0 / (RRF_K + i + 1.0);
            item.put("type_normalized_score", normalized);
            item.put("type_rrf_score", rrfScore);
        }
    }

    private void addTypedResultsWithRrf(List<Map<String, Object>> merged, List<Map<String, Object>> results) {
        for (Map<String, Object> item : results) {
            double normalized = (Double) item.getOrDefault("type_normalized_score", 0.0);
            double rrfScore = (Double) item.getOrDefault("type_rrf_score", 0.0);
            item.put("final_score", normalized * 0.85 + rrfScore * 0.15);
            item.put("score", item.get("final_score"));
            merged.add(item);
        }
    }

    private void applyQwenRerank(String keyword, List<Map<String, Object>> results) {
        if (!isDashScopeConfigured() || keyword == null || keyword.trim().isEmpty() || results.isEmpty()) {
            return;
        }
        int rerankSize = Math.min(results.size(), RERANK_CANDIDATE_LIMIT);
        List<Map<String, Object>> candidates = new ArrayList<>(results.subList(0, rerankSize));
        try {
            List<RerankScore> scores = rerankWithQwen(keyword, candidates);
            if (scores.isEmpty()) {
                return;
            }
            Map<Integer, Double> scoreMap = new HashMap<>();
            for (RerankScore score : scores) {
                if (score.index >= 0 && score.index < candidates.size()) {
                    scoreMap.put(score.index, score.score);
                    candidates.get(score.index).put("rerank_score", score.score);
                }
            }
            candidates.sort((a, b) -> Double.compare(
                    (Double) b.getOrDefault("rerank_score", 0.0),
                    (Double) a.getOrDefault("rerank_score", 0.0)));
            for (int i = 0; i < candidates.size(); i++) {
                Map<String, Object> item = candidates.get(i);
                double rerankScore = (Double) item.getOrDefault("rerank_score", 0.0);
                double originalScore = (Double) item.getOrDefault("final_score", item.getOrDefault("score", 0.0));
                item.put("final_score", rerankScore * 0.80 + originalScore * 0.20);
                item.put("score", item.get("final_score"));
            }
            results.subList(0, rerankSize).clear();
            results.addAll(0, candidates);
        } catch (Exception e) {
            System.out.println("Qwen rerank skipped: " + e.getMessage());
        }
    }

    private List<RerankScore> rerankWithQwen(String query, List<Map<String, Object>> candidates) throws IOException {
        List<RerankScore> rerankScores = new ArrayList<>();
        String apiKey = dashScopeApiKey();
        if (apiKey.isEmpty()) {
            return rerankScores;
        }
        Map<String, Object> input = new HashMap<>();
        input.put("query", query);
        List<String> documents = new ArrayList<>();
        for (Map<String, Object> candidate : candidates) {
            documents.add(buildRerankDocument(candidate));
        }
        input.put("documents", documents);

        Map<String, Object> parameters = new HashMap<>();
        parameters.put("return_documents", false);
        parameters.put("top_n", candidates.size());

        Map<String, Object> body = new HashMap<>();
        body.put("model", dashScopeModel("dashscope.rerank.model", "DASHSCOPE_RERANK_MODEL", DEFAULT_RERANK_MODEL));
        body.put("input", input);
        body.put("parameters", parameters);

        com.alibaba.fastjson.JSONObject response = postDashScope(DASHSCOPE_RERANK_URL, apiKey, body);
        com.alibaba.fastjson.JSONArray results = null;
        com.alibaba.fastjson.JSONObject output = response.getJSONObject("output");
        if (output != null) {
            results = output.getJSONArray("results");
        }
        if (results == null) {
            results = response.getJSONArray("results");
        }
        if (results == null) {
            return rerankScores;
        }
        for (int i = 0; i < results.size(); i++) {
            com.alibaba.fastjson.JSONObject item = results.getJSONObject(i);
            int index = item.getIntValue("index");
            double score = item.containsKey("relevance_score")
                    ? item.getDoubleValue("relevance_score")
                    : item.getDoubleValue("score");
            rerankScores.add(new RerankScore(index, score));
        }
        return rerankScores;
    }

    private String buildRerankDocument(Map<String, Object> item) {
        String title = String.valueOf(item.getOrDefault("title", item.getOrDefault("qzh", "")));
        String snippet = String.valueOf(item.getOrDefault("snippet", item.getOrDefault("azh", "")));
        String domain = String.valueOf(item.getOrDefault("qdomain", ""));
        return (title + "\n" + domain + "\n" + snippet).trim();
    }

    private static class RerankScore {
        private final int index;
        private final double score;

        private RerankScore(int index, double score) {
            this.index = index;
            this.score = score;
        }
    }

    private void attachQuestionMetadata(Map<String, Object> answerData, Map<String, Object> questionMeta) {
        if (questionMeta == null) {
            return;
        }
        answerData.putIfAbsent("qid", questionMeta.get("qid"));
        answerData.putIfAbsent("qzh", questionMeta.get("qzh"));
        answerData.putIfAbsent("qdomain", questionMeta.get("qdomain"));
    }

    private Map<String, Map<String, Object>> buildAidQuestionMetadata() throws IOException {
        SearchRequest searchRequest = new SearchRequest(INDEX_QUESTION);
        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
        sourceBuilder.query(QueryBuilders.matchAllQuery());
        sourceBuilder.size(10000);
        sourceBuilder.fetchSource(new String[] { "qid", "qzh", "qdomain", "qanswers" }, null);
        searchRequest.source(sourceBuilder);

        SearchResponse searchResponse = client.search(searchRequest, RequestOptions.DEFAULT);
        Map<String, Map<String, Object>> aidQuestionMap = new HashMap<>();
        for (SearchHit hit : searchResponse.getHits().getHits()) {
            Map<String, Object> question = hit.getSourceAsMap();
            Map<String, Object> metadata = new HashMap<>();
            metadata.put("qid", question.getOrDefault("qid", ""));
            metadata.put("qzh", question.getOrDefault("qzh", ""));
            metadata.put("qdomain", question.getOrDefault("qdomain", ""));

            for (String aid : extractIdList(question.get("qanswers"))) {
                aidQuestionMap.putIfAbsent(aid, metadata);
            }
        }
        return aidQuestionMap;
    }

    private Map<String, Map<String, Object>> getAidQuestionMetadata() throws IOException {
        long now = System.currentTimeMillis();
        if (!aidQuestionCache.isEmpty() && now - aidQuestionCacheLoadedAt < AID_QUESTION_CACHE_TTL_MS) {
            return aidQuestionCache;
        }
        synchronized (aidQuestionCache) {
            now = System.currentTimeMillis();
            if (!aidQuestionCache.isEmpty() && now - aidQuestionCacheLoadedAt < AID_QUESTION_CACHE_TTL_MS) {
                return aidQuestionCache;
            }
            Map<String, Map<String, Object>> loaded = buildAidQuestionMetadata();
            aidQuestionCache.clear();
            aidQuestionCache.putAll(loaded);
            aidQuestionCacheLoadedAt = now;
        }
        return aidQuestionCache;
    }

    private Map<String, Map<String, Object>> buildAidQuestionMetadata(List<Question> questionList) {
        Map<String, Map<String, Object>> aidQuestionMap = new HashMap<>();
        for (Question question : questionList) {
            Map<String, Object> metadata = new HashMap<>();
            metadata.put("qid", question.getQid());
            metadata.put("qzh", question.getQzh());
            metadata.put("qdomain", question.getQdomain());
            for (String aid : extractIdList(question.getQanswers())) {
                aidQuestionMap.putIfAbsent(aid, metadata);
            }
        }
        return aidQuestionMap;
    }

    private List<String> extractIdList(Object idValue) {
        List<String> idList = new ArrayList<>();
        if (idValue == null) {
            return idList;
        }
        if (idValue instanceof Iterable) {
            for (Object value : (Iterable<?>) idValue) {
                if (value != null) {
                    idList.add(String.valueOf(value));
                }
            }
            return idList;
        }
        Matcher matcher = Pattern.compile("[a-zA-Z0-9]+").matcher(String.valueOf(idValue));
        while (matcher.find()) {
            idList.add(matcher.group());
        }
        return idList;
    }

    private double maxScore(List<Map<String, Object>> results) {
        double maxScore = 0.0;
        for (Map<String, Object> item : results) {
            maxScore = Math.max(maxScore, (Double) item.getOrDefault("raw_score", 0.0));
        }
        return maxScore;
    }

    private Map<String, Double> buildQuestionScoreMap(List<Map<String, Object>> questionResults) {
        Map<String, Double> questionScoreMap = new HashMap<>();
        for (Map<String, Object> item : questionResults) {
            String qid = String.valueOf(item.getOrDefault("qid", ""));
            if (qid.isEmpty()) {
                continue;
            }
            double score = (Double) item.getOrDefault("combined_score", 0.0);
            questionScoreMap.put(qid, Math.max(questionScoreMap.getOrDefault(qid, 0.0), score));
        }
        return questionScoreMap;
    }

    private double maxCombinedScore(List<Map<String, Object>> results) {
        double maxScore = 0.0;
        for (Map<String, Object> item : results) {
            maxScore = Math.max(maxScore, (Double) item.getOrDefault("combined_score", 0.0));
        }
        return maxScore;
    }

    private double normalizeScore(double score, double maxScore) {
        if (maxScore <= 0.0) {
            return 0.0;
        }
        return score / maxScore;
    }

    private double semanticSimilarity(String query, String text) {
        if (query == null || text == null || query.trim().isEmpty() || text.trim().isEmpty()) {
            return 0.0;
        }

        String queryCore = normalizeSemanticText(query);
        String textCore = normalizeSemanticText(text);
        if (queryCore.isEmpty() || textCore.isEmpty()) {
            return 0.0;
        }
        if (textCore.contains(queryCore)) {
            return 1.0;
        }

        Set<String> queryTokens = semanticTokens(queryCore);
        Set<String> textTokens = semanticTokens(textCore);
        if (queryTokens.isEmpty() || textTokens.isEmpty()) {
            return 0.0;
        }

        int intersection = 0;
        for (String token : queryTokens) {
            if (textTokens.contains(token)) {
                intersection++;
            }
        }
        return (double) intersection / queryTokens.size();
    }

    private boolean exactCoreMatch(String query, String text) {
        String queryCore = normalizeSemanticText(query);
        String textCore = normalizeSemanticText(text);
        return !queryCore.isEmpty() && textCore.contains(queryCore);
    }

    private double answerLengthQualityScore(String answer) {
        if (answer == null) {
            return 0.0;
        }
        int length = answer.replaceAll("\\s+", "").length();
        if (length <= 0) {
            return 0.0;
        }
        if (length < 15) {
            return length / 15.0 * 0.2;
        }
        if (length < 30) {
            return 0.2 + (length - 15) / 15.0 * 0.25;
        }
        if (length < 60) {
            return 0.45 + (length - 30) / 30.0 * 0.25;
        }
        if (length < 120) {
            return 0.7 + (length - 60) / 60.0 * 0.2;
        }
        if (length < 220) {
            return 0.9 + (length - 120) / 100.0 * 0.1;
        }
        return 1.0;
    }

    private double answerQualityPenalty(String answer) {
        if (answer == null || answer.trim().isEmpty()) {
            return 0.3;
        }
        String compactAnswer = answer.replaceAll("\\s+", "");
        String normalizedAnswer = normalizeSemanticText(answer);
        double penalty = 0.0;
        if (normalizedAnswer.length() < 12) {
            penalty += 0.12;
        }
        if (Pattern.compile("(.{2,10})就是让\\1").matcher(compactAnswer).find()) {
            penalty += 0.28;
        }
        if (compactAnswer.contains("大概就是")
                || compactAnswer.contains("简单来说就是")
                || compactAnswer.contains("差不多就是")) {
            penalty += 0.08;
        }
        if (normalizedAnswer.contains("没什么特别")
                || normalizedAnswer.contains("不知道")
                || normalizedAnswer.contains("不清楚")
                || normalizedAnswer.contains("随便")
                || normalizedAnswer.contains("差不多")) {
            penalty += 0.25;
        }
        return penalty;
    }

    private String normalizeSemanticText(String text) {
        if (text == null) {
            return "";
        }
        String normalized = text.toLowerCase()
                .replaceAll("[+|()\"'\\[\\]{}:：,，.。?？!！;；、\\s]", "");
        String[] stopWords = new String[] {
                "什么是", "是什么", "什么", "哪些", "怎么", "如何", "为什么", "为何", "以及", "它的", "它",
                "这个", "一种", "一个", "的是", "就是", "是", "的", "了", "和", "与", "及", "在", "中"
        };
        for (String stopWord : stopWords) {
            normalized = normalized.replace(stopWord, "");
        }
        return normalized;
    }

    private Set<String> semanticTokens(String text) {
        Set<String> tokens = new HashSet<>();
        if (text == null || text.isEmpty()) {
            return tokens;
        }
        Matcher wordMatcher = Pattern.compile("[a-zA-Z0-9]{2,}").matcher(text);
        while (wordMatcher.find()) {
            tokens.add(wordMatcher.group());
        }

        List<Character> cjkChars = new ArrayList<>();
        for (char c : text.toCharArray()) {
            if (isCjk(c)) {
                cjkChars.add(c);
                tokens.add(String.valueOf(c));
            }
        }
        for (int i = 0; i < cjkChars.size() - 1; i++) {
            tokens.add("" + cjkChars.get(i) + cjkChars.get(i + 1));
        }
        for (int i = 0; i < cjkChars.size() - 2; i++) {
            tokens.add("" + cjkChars.get(i) + cjkChars.get(i + 1) + cjkChars.get(i + 2));
        }
        return tokens;
    }

    private boolean isCjk(char c) {
        return c >= '\u4e00' && c <= '\u9fff';
    }

    private double keywordCoverageBoost(String keyword, String text) {
        if (keyword == null || text == null || keyword.trim().isEmpty() || text.trim().isEmpty()) {
            return 0.0;
        }
        String cleanKeyword = keyword.replaceAll("[+|()\"']", " ").replace("-", " ");
        String lowerText = text.toLowerCase();
        String[] tokens = cleanKeyword.trim().split("\\s+");
        int total = 0;
        int matched = 0;
        for (String token : tokens) {
            if (token == null || token.trim().isEmpty()) {
                continue;
            }
            total++;
            if (lowerText.contains(token.toLowerCase())) {
                matched++;
            }
        }
        if (total == 0) {
            return 0.0;
        }
        return (double) matched / total;
    }

    private String highlightOrEscaped(SearchHit hit, String fieldName, String fallback, int maxLength) {
        HighlightField highlightField = hit.getHighlightFields().get(fieldName);
        if (highlightField != null && highlightField.fragments() != null && highlightField.fragments().length > 0) {
            return highlightField.fragments()[0].string();
        }
        return escapeHtml(shorten(fallback, maxLength));
    }

    private String shorten(String text, int maxLength) {
        if (text == null) {
            return "";
        }
        if (text.length() <= maxLength) {
            return text;
        }
        return text.substring(0, maxLength) + "...";
    }

    private String escapeHtml(String text) {
        if (text == null) {
            return "";
        }
        return text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#39;");
    }

    public List<Map<String, Object>> searchAnswer(String qid) throws IOException {
        // 1. 条件搜索 insurance_question，查出问题详情
        SearchRequest questionRequest = new SearchRequest(INDEX_QUESTION); // 请确保 INDEX_QUESTION 变量存在
        SearchSourceBuilder questionSourceBuilder = new SearchSourceBuilder();
        questionSourceBuilder.query(QueryBuilders.termQuery("qid", qid));
        questionRequest.source(questionSourceBuilder);

        SearchResponse questionResponse = client.search(questionRequest, RequestOptions.DEFAULT); // 确保 client 变量存在

        if (questionResponse.getHits().getHits().length == 0) {
            System.out.println("【诊断 1 失败】: 在 insurance_question 库中没有找到 qid 为 " + qid + " 的问题！");
            return new ArrayList<>();
        }

        // 获取问题的具体字段数据
        Map<String, Object> questionData = questionResponse.getHits().getHits()[0].getSourceAsMap();
        String qdomain = (String) questionData.getOrDefault("qdomain", "");
        String qzh = (String) questionData.getOrDefault("qzh", "");
        String qen = (String) questionData.getOrDefault("qen", "");
        String qanswers = (String) questionData.getOrDefault("qanswers", "");

        System.out.println("【诊断 1 成功】: 找到问题 -> " + qzh);

        // 2. 提取出该问题对应的所有的答案 ID (aid)
        List<String> aidList = new ArrayList<>();
        if (qanswers != null && !qanswers.isEmpty()) {
            Matcher m = Pattern.compile("[a-zA-Z0-9]+").matcher(qanswers);
            while (m.find()) {
                aidList.add(m.group());
            }
        }
        if (!aidList.isEmpty()) {
            String questionText = (qzh + " " + qdomain).trim();
            List<Map<String, Object>> answerResults = searchAnswerDetailCandidates(qid, qdomain, qzh, qen, aidList, questionText);
            normalizeAnswerDetailScores(answerResults);
            applyQwenAnswerDetailRerank(questionText, answerResults);
            scoreAnswerDetailResults(answerResults);
            answerResults.sort((a, b) -> Double.compare(
                    (Double) b.getOrDefault("algorithm_score", 0.0),
                    (Double) a.getOrDefault("algorithm_score", 0.0)));
            return answerResults;
        }
        List<Map<String, Object>> finalResultList = new ArrayList<>();

        // 3. 去保险答案库搜索并计算基础分数
        if (!aidList.isEmpty()) {
            SearchRequest answerRequest = new SearchRequest(INDEX_ANSWER);
            SearchSourceBuilder answerSourceBuilder = new SearchSourceBuilder();

            BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();
            boolQuery.filter(QueryBuilders.termsQuery("aid", aidList));

            if (qzh != null && !qzh.trim().isEmpty()) {
                boolQuery.should(QueryBuilders.matchQuery("azh", qzh));
            }

            // ES 脚本算分 (基础匹配 * 对数长度奖励)
            String scriptCode = "double baseScore = _score; " +
                    "double textLen = 1.0; " +
                    "if (params._source['azh'] != null) { " +
                    "   textLen = params._source['azh'].length(); " +
                    "} " +
                    "double lengthBonus = Math.log10(textLen + 10.0); " +
                    "return baseScore * lengthBonus;";

            Script script = new Script(Script.DEFAULT_SCRIPT_TYPE, "painless", scriptCode, Collections.emptyMap());
            ScriptScoreQueryBuilder customizedScoreQuery = QueryBuilders.scriptScoreQuery(boolQuery, script);

            answerSourceBuilder.query(customizedScoreQuery);
            answerSourceBuilder.timeout(new TimeValue(60, TimeUnit.SECONDS));
            answerRequest.source(answerSourceBuilder);

            SearchResponse answerResponse = client.search(answerRequest, RequestOptions.DEFAULT);

            // 4. 解析结果存入 List
            for (SearchHit hit : answerResponse.getHits().getHits()) {
                Map<String, Object> answerData = hit.getSourceAsMap();
                Map<String, Object> map = new HashMap<>();
                map.put("qid", qid);
                map.put("qdomain", qdomain);
                map.put("qzh", qzh);
                map.put("qen", qen);
                map.put("aid", answerData.get("aid"));
                map.put("azh", answerData.getOrDefault("azh", ""));
                map.put("aen", answerData.get("aen"));
                map.put("match_score", (double) hit.getScore()); // 保存 ES 的基础评分

                finalResultList.add(map);
            }

            // ====================================================================
            // 5. 核心算法：基于 Min-Max 归一化的多特征融合排序 (MCDA 算法)
            // ====================================================================
            System.out.println("【开始执行多特征特征提取与归一化】...");

            // 第一步：定义变量，用来记录各个特征组内的最大值和最小值
            double maxBm25 = -Double.MAX_VALUE, minBm25 = Double.MAX_VALUE;
            double maxLength = -Double.MAX_VALUE, minLength = Double.MAX_VALUE;
            double maxStruct = -Double.MAX_VALUE, minStruct = Double.MAX_VALUE;
            double maxVector = -Double.MAX_VALUE, minVector = Double.MAX_VALUE;

            // 1. 第一次遍历：计算原始特征分，并寻找极大/极小值
            for (Map<String, Object> map : finalResultList) {
                String answer = (String) map.getOrDefault("azh", "");
                String question = (String) map.getOrDefault("qzh", "");

                // 特征 1：原始 BM25 分数
                double rawBm25 = (Double) map.getOrDefault("match_score", 0.0);

                // 特征 2：原始长度对数
                double rawLength = answerLengthQualityScore(answer);

                // 特征 3：原始结构密度
                int punctuationCount = 0;
                String punctuations = "，。！？；、（）【】《》";
                for (char c : answer.toCharArray()) {
                    if (punctuations.indexOf(c) != -1)
                        punctuationCount++;
                }
                double rawStruct = Math.log1p(punctuationCount);

                // 特征 4：原始余弦向量相似度
                double rawVector = calculateCosineSimilarity(question, answer);

                // 暂存原始分，免得第二次遍历再算一遍
                map.put("raw_bm25", rawBm25);
                map.put("raw_length", rawLength);
                map.put("raw_struct", rawStruct);
                map.put("raw_vector", rawVector);

                // 更新各维度的最大最小值
                maxBm25 = Math.max(maxBm25, rawBm25);
                minBm25 = Math.min(minBm25, rawBm25);
                maxLength = Math.max(maxLength, rawLength);
                minLength = Math.min(minLength, rawLength);
                maxStruct = Math.max(maxStruct, rawStruct);
                minStruct = Math.min(minStruct, rawStruct);
                maxVector = Math.max(maxVector, rawVector);
                minVector = Math.min(minVector, rawVector);
            }

            // 权重配置 (现在所有特征都在 0-1 之间，权重终于具有了绝对的决定权！)
            final double WEIGHT_BM25 = 2.5; // 基础文本匹配
            final double WEIGHT_LENGTH = 2.0; // 文本信息量
            final double WEIGHT_STRUCT = 1.0; // 学术结构性
            final double WEIGHT_VECTOR = 1.0; // 真实语义重叠  

            // 2. 第二次遍历：执行 Min-Max 归一化，并乘以权重计算最终得分
            for (Map<String, Object> map : finalResultList) {
                double rawBm25 = (Double) map.get("raw_bm25");
                double rawLength = (Double) map.get("raw_length");
                double rawStruct = (Double) map.get("raw_struct");
                double rawVector = (Double) map.get("raw_vector");

                // 自定义安全归一化方法：防止所有候选答案某一特征一模一样导致除以 0 的异常
                double normBm25 = safeNormalize(rawBm25, minBm25, maxBm25);
                double normLength = safeNormalize(rawLength, minLength, maxLength);
                double normStruct = safeNormalize(rawStruct, minStruct, maxStruct);
                double normVector = safeNormalize(rawVector, minVector, maxVector);

                // 综合打分公式：所有基础项此时都在 0.0 ~ 1.0 之间
                double finalQualityScore = (WEIGHT_BM25 * normBm25)
                        + (WEIGHT_LENGTH * normLength)
                        + (WEIGHT_STRUCT * normStruct)
                        + (WEIGHT_VECTOR * normVector);

                map.put("algorithm_score", finalQualityScore);

                // 清理掉为了计算临时存的原始变量（保持返回给前端的数据干净）
                map.remove("raw_bm25");
                map.remove("raw_length");
                map.remove("raw_struct");
                map.remove("raw_vector");
            }

            // ====================================================================
            // 6. 根据算法算出的综合分数进行倒序排列
            // ====================================================================
            finalResultList.sort((map1, map2) -> {
                Double score1 = (Double) map1.get("algorithm_score");
                Double score2 = (Double) map2.get("algorithm_score");
                return Double.compare(score2, score1);
            });
        } else {
            System.out.println("【诊断 2 失败】: 问题的 qanswers 字段没有找到任何有效的 aid！");
        }
        return finalResultList;
    }

    private List<Map<String, Object>> searchAnswerDetailCandidates(String qid, String qdomain, String qzh, String qen,
            List<String> aidList, String questionText) throws IOException {
        SearchRequest answerRequest = new SearchRequest(INDEX_ANSWER);
        SearchSourceBuilder answerSourceBuilder = new SearchSourceBuilder();
        answerSourceBuilder.from(0).size(Math.max(aidList.size(), 10));
        answerSourceBuilder.trackTotalHits(true);

        BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();
        boolQuery.filter(QueryBuilders.termsQuery("aid", aidList));
        if (questionText != null && !questionText.trim().isEmpty()) {
            boolQuery.should(QueryBuilders.matchQuery("azh", questionText));
            boolQuery.should(QueryBuilders.matchQuery("aen", questionText).boost(0.5f));
        }
        answerSourceBuilder.query(boolQuery);
        answerSourceBuilder.timeout(new TimeValue(60, TimeUnit.SECONDS));
        answerRequest.source(answerSourceBuilder);

        SearchResponse answerResponse = client.search(answerRequest, RequestOptions.DEFAULT);
        List<Map<String, Object>> results = new ArrayList<>();
        double[] queryVector = createEmbedding(questionText, "query");
        for (SearchHit hit : answerResponse.getHits().getHits()) {
            Map<String, Object> answerData = hit.getSourceAsMap();
            String answer = String.valueOf(answerData.getOrDefault("azh", ""));
            Map<String, Object> map = new HashMap<>();
            map.put("qid", qid);
            map.put("qdomain", qdomain);
            map.put("qzh", qzh);
            map.put("qen", qen);
            map.put("aid", answerData.get("aid"));
            map.put("azh", answer);
            map.put("aen", answerData.get("aen"));
            map.put("match_score", (double) hit.getScore());
            map.put("bm25_score", (double) hit.getScore());
            map.put("embedding_score", answerDetailEmbeddingScore(answerData, answer, queryVector));
            map.put("semantic_score", semanticSimilarity(questionText, answer));
            map.put("answer_question_fit", semanticSimilarity(qzh, answer));
            map.put("length_score", answerLengthQualityScore(answer));
            map.put("quality_penalty", answerQualityPenalty(answer));
            results.add(map);
        }
        return results;
    }

    private double answerDetailEmbeddingScore(Map<String, Object> answerData, String answer, double[] queryVector) {
        Object storedVector = answerData.get(FIELD_ANSWER_VECTOR);
        if (storedVector instanceof List) {
            return cosineSimilarity(queryVector, toDoubleArray((List<?>) storedVector));
        }
        return cosineSimilarity(queryVector, createEmbedding(answer, "document"));
    }

    private void normalizeAnswerDetailScores(List<Map<String, Object>> results) {
        double maxBm25 = 0.0;
        double maxEmbedding = 0.0;
        double maxSemantic = 0.0;
        for (Map<String, Object> item : results) {
            maxBm25 = Math.max(maxBm25, (Double) item.getOrDefault("bm25_score", 0.0));
            maxEmbedding = Math.max(maxEmbedding, (Double) item.getOrDefault("embedding_score", 0.0));
            maxSemantic = Math.max(maxSemantic, (Double) item.getOrDefault("semantic_score", 0.0));
        }
        for (Map<String, Object> item : results) {
            item.put("normalized_bm25_score", normalizeScore((Double) item.getOrDefault("bm25_score", 0.0), maxBm25));
            item.put("normalized_embedding_score", normalizeScore((Double) item.getOrDefault("embedding_score", 0.0), maxEmbedding));
            item.put("normalized_semantic_score", normalizeScore((Double) item.getOrDefault("semantic_score", 0.0), maxSemantic));
        }
    }

    private void applyQwenAnswerDetailRerank(String questionText, List<Map<String, Object>> results) {
        if (!isDashScopeConfigured() || results.isEmpty()) {
            return;
        }
        try {
            List<RerankScore> scores = rerankWithQwen(questionText, results);
            for (RerankScore score : scores) {
                if (score.index >= 0 && score.index < results.size()) {
                    results.get(score.index).put("rerank_score", score.score);
                }
            }
        } catch (Exception e) {
            System.out.println("Qwen answer detail rerank skipped: " + e.getMessage());
        }
    }

    private void scoreAnswerDetailResults(List<Map<String, Object>> results) {
        double maxRerank = 0.0;
        for (Map<String, Object> item : results) {
            maxRerank = Math.max(maxRerank, (Double) item.getOrDefault("rerank_score", 0.0));
        }
        for (Map<String, Object> item : results) {
            double bm25Score = (Double) item.getOrDefault("normalized_bm25_score", 0.0);
            double embeddingScore = (Double) item.getOrDefault("normalized_embedding_score", 0.0);
            double semanticScore = (Double) item.getOrDefault("normalized_semantic_score", 0.0);
            double rerankScore = normalizeScore((Double) item.getOrDefault("rerank_score", 0.0), maxRerank);
            double qualityScore = (Double) item.getOrDefault("length_score", 0.0) * 0.70
                    + (Double) item.getOrDefault("answer_question_fit", 0.0) * 0.30;
            double penalty = (Double) item.getOrDefault("quality_penalty", 0.0);
            double algorithmScore = bm25Score * 0.25
                    + embeddingScore * 0.25
                    + rerankScore * 0.30
                    + semanticScore * 0.10
                    + qualityScore * 0.10
                    - penalty;
            item.put("algorithm_score", Math.max(0.0, algorithmScore));
        }
    }

    private double[] toDoubleArray(List<?> values) {
        double[] vector = new double[values.size()];
        for (int i = 0; i < values.size(); i++) {
            Object value = values.get(i);
            if (value instanceof Number) {
                vector[i] = ((Number) value).doubleValue();
            }
        }
        return vector;
    }

    private double cosineSimilarity(double[] vector1, double[] vector2) {
        if (vector1 == null || vector2 == null || vector1.length == 0 || vector1.length != vector2.length) {
            return 0.0;
        }
        double dotProduct = 0.0;
        double normA = 0.0;
        double normB = 0.0;
        for (int i = 0; i < vector1.length; i++) {
            dotProduct += vector1[i] * vector2[i];
            normA += vector1[i] * vector1[i];
            normB += vector2[i] * vector2[i];
        }
        if (normA == 0.0 || normB == 0.0) {
            return 0.0;
        }
        return (dotProduct / (Math.sqrt(normA) * Math.sqrt(normB)) + 1.0) / 2.0;
    }

    /**
     * 【内部算法方法】计算两个字符串的向量余弦相似度 (Cosine Vector Similarity)
     * 原理：将文本转化为词频向量空间，计算向量点积与模长的比值。
     */
    private double safeNormalize(double value, double min, double max) {
        if (max - min == 0.0) {
            return 0.5; // 如果大家都一样，或者只有一个答案，默认给中间分
        }
        return (value - min) / (max - min);
    }

    private double calculateCosineSimilarity(String text1, String text2) {
        if (text1 == null || text2 == null || text1.isEmpty() || text2.isEmpty()) {
            return 0.0;
        }

        // 1. 构建向量空间 (Vocabulary)
        Map<Character, Integer> vector1 = new HashMap<>();
        Map<Character, Integer> vector2 = new HashMap<>();
        Set<Character> vocabulary = new HashSet<>();

        for (char c : text1.toCharArray()) {
            vector1.put(c, vector1.getOrDefault(c, 0) + 1);
            vocabulary.add(c);
        }
        for (char c : text2.toCharArray()) {
            vector2.put(c, vector2.getOrDefault(c, 0) + 1);
            vocabulary.add(c);
        }

        // 2. 计算向量点积 (Dot Product) 和 模长 (Magnitude)
        double dotProduct = 0.0;
        double normA = 0.0;
        double normB = 0.0;

        for (char c : vocabulary) {
            int v1 = vector1.getOrDefault(c, 0);
            int v2 = vector2.getOrDefault(c, 0);

            dotProduct += v1 * v2;
            normA += v1 * v1;
            normB += v2 * v2;
        }

        if (normA == 0.0 || normB == 0.0) {
            return 0.0;
        }

        // 3. 返回余弦值：cos(θ) = (A·B) / (||A|| * ||B||)
        // 结果范围在 0.0 到 1.0 之间，越接近 1.0 语义重叠度越高
        return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
    }

    private void ensureQaIndices() throws IOException {
        ensureIndexWithVector(INDEX_QUESTION, FIELD_QUESTION_VECTOR);
        ensureIndexWithVector(INDEX_ANSWER, FIELD_ANSWER_VECTOR);
    }

    private void ensureIndexWithVector(String indexName, String vectorField) throws IOException {
        GetIndexRequest getIndexRequest = new GetIndexRequest();
        getIndexRequest.indices(indexName);
        String mapping = vectorMapping(vectorField);
        if (!client.indices().exists(getIndexRequest, RequestOptions.DEFAULT)) {
            CreateIndexRequest createIndexRequest = new CreateIndexRequest(indexName);
            createIndexRequest.mapping(mapping, XContentType.JSON);
            CreateIndexResponse response = client.indices().create(createIndexRequest, RequestOptions.DEFAULT);
            if (!response.isAcknowledged()) {
                throw new IOException("Failed to create index " + indexName);
            }
            return;
        }
        try {
            PutMappingRequest putMappingRequest = new PutMappingRequest(indexName);
            putMappingRequest.source(mapping, XContentType.JSON);
            AcknowledgedResponse response = client.indices().putMapping(putMappingRequest, RequestOptions.DEFAULT);
            if (!response.isAcknowledged()) {
                System.out.println("Vector mapping update was not acknowledged for index " + indexName);
            }
        } catch (Exception e) {
            System.out.println("Vector mapping update skipped for index " + indexName + ": " + e.getMessage());
        }
    }

    private String vectorMapping(String vectorField) {
        return "{"
                + "\"properties\":{"
                + "\"" + vectorField + "\":{\"type\":\"dense_vector\",\"dims\":" + EMBEDDING_DIMENSION + "}"
                + "}"
                + "}";
    }

    private double[] createEmbedding(String text) {
        return createEmbedding(text, "document");
    }

    private double[] createEmbedding(String text, String textType) {
        if (isDashScopeConfigured()) {
            try {
                return createQwenEmbedding(text, textType);
            } catch (Exception e) {
                System.out.println("Qwen embedding skipped: " + e.getMessage());
            }
        }
        return createLocalEmbedding(text);
    }

    private double[] createQwenEmbedding(String text, String textType) throws IOException {
        String apiKey = dashScopeApiKey();
        Map<String, Object> input = new HashMap<>();
        List<String> texts = new ArrayList<>();
        texts.add(text == null ? "" : text);
        input.put("texts", texts);

        Map<String, Object> parameters = new HashMap<>();
        parameters.put("text_type", textType == null ? "document" : textType);
        parameters.put("dimension", EMBEDDING_DIMENSION);

        Map<String, Object> body = new HashMap<>();
        body.put("model", dashScopeModel("dashscope.embedding.model", "DASHSCOPE_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL));
        body.put("input", input);
        body.put("parameters", parameters);

        com.alibaba.fastjson.JSONObject response = postDashScope(DASHSCOPE_EMBEDDING_URL, apiKey, body);
        com.alibaba.fastjson.JSONObject output = response.getJSONObject("output");
        if (output == null) {
            throw new IOException("Missing embedding output");
        }
        com.alibaba.fastjson.JSONArray embeddings = output.getJSONArray("embeddings");
        if (embeddings == null || embeddings.isEmpty()) {
            throw new IOException("Missing embedding vector");
        }
        com.alibaba.fastjson.JSONObject first = embeddings.getJSONObject(0);
        com.alibaba.fastjson.JSONArray embedding = first.getJSONArray("embedding");
        if (embedding == null || embedding.size() != EMBEDDING_DIMENSION) {
            throw new IOException("Unexpected embedding dimension");
        }
        double[] vector = new double[EMBEDDING_DIMENSION];
        for (int i = 0; i < embedding.size(); i++) {
            vector[i] = embedding.getDoubleValue(i);
        }
        return vector;
    }

    private double[] createLocalEmbedding(String text) {
        double[] vector = new double[EMBEDDING_DIMENSION];
        String normalized = normalizeSemanticText(text);
        if (normalized.isEmpty()) {
            return vector;
        }
        Set<String> tokens = semanticTokens(normalized);
        if (tokens.isEmpty()) {
            tokens.add(normalized);
        }
        for (String token : tokens) {
            int hash = token.hashCode();
            int index = Math.floorMod(hash, EMBEDDING_DIMENSION);
            double sign = (hash & 1) == 0 ? 1.0 : -1.0;
            vector[index] += sign;
        }
        double norm = 0.0;
        for (double value : vector) {
            norm += value * value;
        }
        if (norm == 0.0) {
            return vector;
        }
        norm = Math.sqrt(norm);
        for (int i = 0; i < vector.length; i++) {
            vector[i] = vector[i] / norm;
        }
        return vector;
    }

    private boolean isDashScopeConfigured() {
        return !dashScopeApiKey().isEmpty();
    }

    private String dashScopeApiKey() {
        String key = System.getProperty("dashscope.api-key");
        if (key == null || key.trim().isEmpty()) {
            key = System.getenv("DASHSCOPE_API_KEY");
        }
        return key == null ? "" : key.trim();
    }

    private String dashScopeModel(String propertyName, String envName, String defaultModel) {
        String model = System.getProperty(propertyName);
        if (model == null || model.trim().isEmpty()) {
            model = System.getenv(envName);
        }
        return model == null || model.trim().isEmpty() ? defaultModel : model.trim();
    }

    private com.alibaba.fastjson.JSONObject postDashScope(String url, String apiKey, Map<String, Object> body)
            throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(30000);
        connection.setDoOutput(true);
        connection.setRequestProperty("Authorization", "Bearer " + apiKey);
        connection.setRequestProperty("Content-Type", "application/json");
        byte[] requestBody = JSON.toJSONString(body).getBytes(StandardCharsets.UTF_8);
        connection.setRequestProperty("Content-Length", String.valueOf(requestBody.length));
        try (OutputStream outputStream = connection.getOutputStream()) {
            outputStream.write(requestBody);
        }
        int status = connection.getResponseCode();
        String responseBody = readResponseBody(status >= 200 && status < 300
                ? connection.getInputStream()
                : connection.getErrorStream());
        if (status < 200 || status >= 300) {
            throw new IOException("DashScope HTTP " + status + ": " + responseBody);
        }
        return JSON.parseObject(responseBody);
    }

    private String readResponseBody(InputStream inputStream) throws IOException {
        if (inputStream == null) {
            return "";
        }
        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line);
            }
        }
        return builder.toString();
    }

    private List<Float> toFloatList(double[] vector) {
        List<Float> values = new ArrayList<>(vector.length);
        for (double value : vector) {
            values.add((float) value);
        }
        return values;
    }

    public boolean writeQAContent() throws IOException {

        ensureQaIndices();

        // write quesitons into ES
        String file_path = "D:/信息检索/questions2.json";
        List<Question> questionList = new JsonParseUtil().parseJson(file_path);
        Map<String, Map<String, Object>> aidQuestionMap = buildAidQuestionMetadata(questionList);

        // 把查询的数据放入 es 中
        BulkRequest request = new BulkRequest();
        request.timeout("2m");

        for (int i = 0; i < questionList.size(); i++) {
            Question question = questionList.get(i);
            Map<String, Object> source = JSON.parseObject(JSON.toJSONString(question));
            source.put(FIELD_QUESTION_VECTOR, toFloatList(createEmbedding(question.getQzh() + " " + question.getQdomain())));
            request.add(
                    new IndexRequest(INDEX_QUESTION)
                            .id(question.getQid())
                            .source(JSON.toJSONString(source), XContentType.JSON));
        }
        BulkResponse bulk = client.bulk(request, RequestOptions.DEFAULT);

        // write answers into ES
        file_path = "D:/信息检索/answers2.json";
        List<Answer> answerList = new JsonParseUtil().parseAnJson(file_path);

        // 把查询的数据放入 es 中
        request = new BulkRequest();
        request.timeout("2m");

        for (int i = 0; i < answerList.size(); i++) {
            Answer answer = answerList.get(i);
            Map<String, Object> source = JSON.parseObject(JSON.toJSONString(answer));
            Map<String, Object> questionMeta = aidQuestionMap.get(answer.getAid());
            attachQuestionMetadata(source, questionMeta);
            String embeddingText = String.valueOf(source.getOrDefault("azh", "")) + " "
                    + String.valueOf(source.getOrDefault("qzh", "")) + " "
                    + String.valueOf(source.getOrDefault("qdomain", ""));
            source.put(FIELD_ANSWER_VECTOR, toFloatList(createEmbedding(embeddingText)));
            request.add(
                    new IndexRequest(INDEX_ANSWER)
                            .id(answer.getAid())
                            .source(JSON.toJSONString(source), XContentType.JSON));

        }
        bulk = client.bulk(request, RequestOptions.DEFAULT);
        aidQuestionCache.clear();
        aidQuestionCache.putAll(aidQuestionMap);
        aidQuestionCacheLoadedAt = System.currentTimeMillis();

        return !bulk.hasFailures();
    }

}
