package com.example.demo;

import com.example.demo.User;
import java.io.IOException;
import java.util.Arrays;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.elasticsearch.action.admin.indices.alias.Alias;
import org.elasticsearch.action.admin.indices.create.CreateIndexRequest;
import org.elasticsearch.action.admin.indices.create.CreateIndexResponse;
import org.elasticsearch.action.admin.indices.delete.DeleteIndexRequest;
import org.elasticsearch.action.admin.indices.get.GetIndexRequest;
import org.elasticsearch.action.admin.indices.get.GetIndexResponse;
import org.elasticsearch.action.bulk.BulkRequest;
import org.elasticsearch.action.bulk.BulkResponse;
import org.elasticsearch.action.delete.DeleteRequest;
import org.elasticsearch.action.delete.DeleteResponse;
import org.elasticsearch.action.get.GetRequest;
import org.elasticsearch.action.get.GetResponse;
import org.elasticsearch.action.index.IndexRequest;
import org.elasticsearch.action.index.IndexResponse;
import org.elasticsearch.action.support.master.AcknowledgedResponse;
import org.elasticsearch.action.update.UpdateRequest;
import org.elasticsearch.action.update.UpdateResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.common.settings.Settings;
import org.elasticsearch.common.xcontent.XContentType;
import org.apache.http.HttpHost;
import org.elasticsearch.client.RestClient;


public class EsDoc {

    public static void main(String[] args) throws IOException {
        // 创建客户端对象
        RestHighLevelClient client = new RestHighLevelClient(
                RestClient.builder(new HttpHost("127.0.0.1", 9200, "http"))
        );
        createDoc(client);
        bulkCreateDoc(client);
//        bulkDeleteDoc(client);
        String str=getDoc(client);

        // 关闭客户端连接
        client.close();
    }

    public static String searchDoc() throws IOException {
        String str;
        // 创建客户端对象
        RestHighLevelClient client = new RestHighLevelClient(
                RestClient.builder(new HttpHost("127.0.0.1", 9200, "http"))
        );

        str=getDoc(client);
        // 关闭客户端连接
        client.close();
        return str;
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