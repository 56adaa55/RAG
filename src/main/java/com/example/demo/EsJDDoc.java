package com.example.demo;

import com.example.demo.pojo.Content;
import com.alibaba.fastjson2.JSON;
import com.example.demo.pojo.Answer;
import com.example.demo.pojo.Question;
import com.example.demo.utils.JsonParseUtil;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.HttpHost;
import org.elasticsearch.action.bulk.BulkRequest;
import org.elasticsearch.action.bulk.BulkResponse;
import org.elasticsearch.action.delete.DeleteRequest;
import org.elasticsearch.action.delete.DeleteResponse;
import org.elasticsearch.action.get.GetRequest;
import org.elasticsearch.action.get.GetResponse;
import org.elasticsearch.action.index.IndexRequest;
import org.elasticsearch.action.index.IndexResponse;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.action.update.UpdateRequest;
import org.elasticsearch.action.update.UpdateResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestClient;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.common.xcontent.XContentType;
import org.elasticsearch.common.unit.TimeValue;
import org.elasticsearch.index.query.*;
import org.elasticsearch.index.query.functionscore.ScriptScoreQueryBuilder;
import org.elasticsearch.script.Script;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.SearchSourceBuilder;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;

public class EsJDDoc {

    public static void main(String[] args) throws IOException {
        // 创建客户端对象
        RestHighLevelClient client = new RestHighLevelClient(
                RestClient.builder(new HttpHost("127.0.0.1", 9200, "http"))
        );
        createDoc(client);
//        bulkCreateDoc(client);
        String str=getDoc(client);

//        str=search_and_create_JDDoc(client);
        writeJDdata(client);

        // 关闭客户端连接
        client.close();
    }


    public static String search_and_create_JDDoc(RestHighLevelClient client) throws IOException {
        String jsonstr,filePath;

        List<Map<String, Object>> list = searchPage(client);
        jsonstr= JSON.toJSONString(list);

        filePath="  ";
        try {
            File file = new File(filePath);
            // 创建文件
            file.createNewFile();
            // 写入文件
            Writer write = new OutputStreamWriter(new FileOutputStream(file), StandardCharsets.UTF_8);
            write.write(jsonstr);
            write.flush();
            write.close();
        } catch (Exception e) {
            e.printStackTrace();
        }

        return jsonstr;
    }

    public static boolean writeJDdata(RestHighLevelClient client) throws IOException {

        //write quesitons into ES
        // String file_path="E:\\数据挖掘\\jddata.json";
        String file_path="E:\\VscodePractice\\sale_match\\cleaned.json";
        List<Content> goodsList = new JsonParseUtil().parseJDJson(file_path);

        //把查询的数据放入 es 中
        BulkRequest request = new BulkRequest();
        request.timeout("2m");

        for (int i = 0; i < goodsList.size(); i++) {
            Content goods = goodsList.get(i);
            request.add(
                    new IndexRequest("jddata")
                            .id(String.valueOf(goods.getTitle()))
                            .source(com.alibaba.fastjson.JSON.toJSONString(goodsList.get(i)), XContentType.JSON));

        }
        BulkResponse bulk = client.bulk(request, RequestOptions.DEFAULT);

        return !bulk.hasFailures();
    }

    //获取ES中的jd数据
    public static List<Map<String, Object>> searchPage(RestHighLevelClient client) throws IOException {
        String keyword="Java";

        //keyword="机器学习";
        // keyword=keyword.getBytes("UTF-8").toString();
        int pageNo = 1;
        int pageSize = 332;

        //条件搜索
        SearchRequest searchRequest = new SearchRequest("jd_goods");
        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();

        //分页
        sourceBuilder.from(pageNo).size(pageSize);
        List<Map<String, Object>> list = new ArrayList<>();

        List<String> keywordlist = new ArrayList<>();

        //集合中加入元素,元素个数不做限制
        keywordlist.add("Java");
        keywordlist.add("Python");
        keywordlist.add("机器问答");
        keywordlist.add("人工智能");

        for (int i = 0; i < keywordlist.size(); i++) {
            keyword=keywordlist.get(i);
            //精准匹配
            // TermQueryBuilder termQuery = QueryBuilders.termQuery("title", keyword);
            MatchQueryBuilder matchQuery = QueryBuilders.matchQuery("title", keyword);


            //sourceBuilder.query(termQuery);
            sourceBuilder.query(matchQuery);
            sourceBuilder.timeout(new TimeValue(60, TimeUnit.SECONDS));
            //执行搜索
            SearchRequest source = searchRequest.source(sourceBuilder);
            SearchResponse searchResponse = client.search(searchRequest, RequestOptions.DEFAULT);
            //解析结果


            for (SearchHit documentFields : searchResponse.getHits().getHits()) {
                list.add(documentFields.getSourceAsMap());
            }
        }
        return list;
    }



    // 创建文档
    public static void createDoc(RestHighLevelClient client) throws IOException {
        // 新增文档 - 请求对象
        IndexRequest request = new IndexRequest();
        // 设置索引及唯一性标识
        request.index("user").id("1001");
        // 创建数据对象
        User user = new User();
        user.setAge(26);
        user.setSex("男");
        user.setName("jak");
        ObjectMapper objectMapper = new ObjectMapper();
        String productJson = objectMapper.writeValueAsString(user);
        // 添加文档数据, 数据格式为Json格式
        request.source(productJson, XContentType.JSON);
        // 客户端发送请求，获取响应对象
        IndexResponse response = client.index(request, RequestOptions.DEFAULT);
        // 打印结果信息
        System.out.println("_index: " + response.getIndex());
        System.out.println("id: " + response.getId());
        System.out.println("_result: " + response.getResult());
    }

    // 修改文档
    public static void updateDoc(RestHighLevelClient client) throws IOException {
        // 修改文档 - 请求对象
        UpdateRequest request = new UpdateRequest();
        // 配置修改参数
        request.index("user").id("1001");
        // 设置请求体，对数据进行修改
        request.doc(XContentType.JSON, "sex", "女");
        // 客户端发送请求，获取响应对象
        UpdateResponse response = client.update(request, RequestOptions.DEFAULT);
        System.out.println("_index: " + response.getIndex());
        System.out.println("_id: " + response.getId());
        System.out.println("_result: " + response.getResult());
    }

    // 查询文档
    public static String getDoc(RestHighLevelClient client) throws IOException {
        // 创建请求对象
        GetRequest request = new GetRequest().index("user").id("1001");
        // 客户端发送请求，获取响应对象
        GetResponse response = client.get(request, RequestOptions.DEFAULT);
        // 打印结果信息
        System.out.println("_index: " + response.getIndex());
        System.out.println("_type: " + response.getType());
        System.out.println("_id: " + response.getId());
        System.out.println("source: " + response.getSourceAsString());
        return response.getSourceAsString();
    }

    // 删除文档
    public static void deleteDoc(RestHighLevelClient client) throws IOException {
        // 创建请求对象
        DeleteRequest request = new DeleteRequest().index("user").id("1");
        // 客户端发送请求，获取响应对象
        DeleteResponse response = client.delete(request, RequestOptions.DEFAULT);
        // 打印信息
        System.out.println(response.toString());
    }

    // 批量新增
    public static void bulkCreateDoc(RestHighLevelClient client) throws IOException {
        // 创建批量新增请求对象
        BulkRequest request = new BulkRequest();
        request.add(new IndexRequest().index("user").id("1001").source(XContentType.JSON, "name", "zhangsan"));
        request.add(new IndexRequest().index("user").id("1002").source(XContentType.JSON, "name", "lisi"));
        request.add(new IndexRequest().index("user").id("1003").source(XContentType.JSON, "name", "wangwu"));
        // 客户端发送请求，获取响应对象
        BulkResponse responses = client.bulk(request, RequestOptions.DEFAULT);
        // 打印结果信息
        System.out.println("took: " + responses.getTook());
        System.out.println("items: " + Arrays.stream(responses.getItems()).toArray().toString());
    }

    // 批量删除
    public static void bulkDeleteDoc(RestHighLevelClient client) throws IOException {
        // 创建批量删除请求对象
        BulkRequest request = new BulkRequest();
        request.add(new DeleteRequest().index("user").id("1001"));
        request.add(new DeleteRequest().index("user").id("1002"));
        request.add(new DeleteRequest().index("user").id("1003"));
        // 客户端发送请求，获取响应对象
        BulkResponse responses = client.bulk(request, RequestOptions.DEFAULT);
        // 打印结果信息
        System.out.println("took: " + responses.getTook());
        System.out.println("items: " + Arrays.toString(responses.getItems()));

    }
}