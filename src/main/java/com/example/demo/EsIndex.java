package com.example.demo;

import java.io.IOException;
import org.elasticsearch.action.admin.indices.alias.Alias;
import org.elasticsearch.action.admin.indices.create.CreateIndexRequest;
import org.elasticsearch.action.admin.indices.create.CreateIndexResponse;
import org.elasticsearch.action.admin.indices.delete.DeleteIndexRequest;
import org.elasticsearch.action.admin.indices.get.GetIndexRequest;
import org.elasticsearch.action.admin.indices.get.GetIndexResponse;
import org.elasticsearch.action.support.master.AcknowledgedResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.common.settings.Settings;
import org.elasticsearch.common.xcontent.XContentType;
import org.apache.http.HttpHost;
import org.elasticsearch.client.RestClient;


public class EsIndex {

    public static void main(String[] args) throws IOException {

        // 创建客户端对象
        RestHighLevelClient client = new RestHighLevelClient(
                RestClient.builder(new HttpHost("127.0.0.1", 9200, "http"))
        );
//        deleteIndex(client);
        createIndex(client);
        // 关闭客户端连接
        client.close();
    }

    // 创建索引
    public static void createIndex(RestHighLevelClient client) throws IOException {
        // 创建索引 - 请求对象
        CreateIndexRequest request = new CreateIndexRequest("user");
        // 发送请求，获取响应
        CreateIndexResponse response = client.indices().create(request, RequestOptions.DEFAULT);
        boolean acknowledged = response.isAcknowledged();
        // 响应状态
        System.out.println("操作状态 = " + acknowledged);
    }

    // 查看索引
    public static void getIndex(RestHighLevelClient client) throws IOException {
        // 查询索引 - 请求对象
        GetIndexRequest request = new GetIndexRequest();
        // 发送请求，获取响应
        GetIndexResponse response = client.indices().get(request, RequestOptions.DEFAULT);
        System.out.println("aliases: " + ((GetIndexResponse) response).getAliases());
        System.out.println("mappings: " + response.getMappings());
        System.out.println("settings: " + response.getSettings());
    }

    // 删除索引
    public static void deleteIndex(RestHighLevelClient client) throws IOException {
        // 删除索引 - 请求对象
        DeleteIndexRequest request = new DeleteIndexRequest("user");
        // 发送请求，获取响应
        AcknowledgedResponse response = client.indices().delete(request, RequestOptions.DEFAULT);
        // 操作结果
        System.out.println("操作结果: " + response.isAcknowledged());
    }
}