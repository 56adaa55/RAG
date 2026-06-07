package com.example.demo;

import com.example.demo.pojo.Content;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;

@Component


public class HtmlParseExample {

    //测试数据

    public static void main(String[] args) throws IOException, InterruptedException {
        //获取请求
        String url = "https://www.phei.com.cn/module/goods/searchkey.jsp?searchKey=%E4%BF%A1%E6%81%AF%E6%A3%80%E7%B4%A2&goodtype=";
        // 解析网页 （Jsou返回的Document就是浏览器的Docuement对象）
        Document document = Jsoup.parse(new URL(url), 30000);
        //获取id，所有在js里面使用的方法在这里都可以使用
        Elements class_elements = document.getElementsByClass("book_list_area");
        //用来计数
        int c = 0;
        for (Element class_el : class_elements) {
            Elements li_elements = class_el.getElementsByTag("li");
            //获取元素中的内容  ，这里的el就是每一个li标签
            for (Element el : li_elements) {
                c++;
                //这里有一点要注意，直接attr使用src是爬不出来的，因为京东使用了img懒加载
                String img = el.getElementsByTag("img").eq(0).attr("src");
                //获取商品的价格，并且只获取第一个text文本内容
                String title = el.getElementsByClass("book_title").text();
                String authorName = el.getElementsByClass("book_author").text();
                String price = el.getElementsByClass("book_price").text();


                System.out.println("========================================");
                System.out.println(title);
                System.out.println(img);
                System.out.println(authorName);
                System.out.println(price);
            }
            System.out.println(c);

            break;

        }
        //获取所有的li元素
    }
}


