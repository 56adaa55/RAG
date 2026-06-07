package com.example.demo.utils;

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


public class HtmlParseUtil {

    public List<Content> parseJD(String keywords) throws IOException {
        String url = "https://search.jd.com/Search?keyword=" + keywords + "&enc=utf-8";
        System.out.println("正在请求网页: " + url);

        // 1. 核心修改：使用 Jsoup.connect 并伪装成真实的谷歌浏览器（User-Agent）
        Document document = Jsoup.connect(url)
                .userAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
                // 如果还是被拦截，你可能需要用浏览器登录京东，把你浏览器的 Cookie 复制下来放到下面这行
                // .cookie("你的cookie名字", "你的cookie值")
                .timeout(30000)
                .get();

        ArrayList<Content> goodList = new ArrayList<>();

        // 2. 核心修改：通过 data-sku 属性来定位每一个商品卡片，因为这个属性对京东来说是必须要有的
        Elements elements = document.select("div[data-sku]");
        System.out.println("成功抓取到商品条数: " + elements.size());

        for (Element el : elements) {
            try {
                // 【提取图片】: 寻找 img 标签，优先取 data-src，没有再取 src
                Element imgElement = el.select("img").first();
                String img = "";
                if (imgElement != null) {
                    img = imgElement.hasAttr("data-src") ? imgElement.attr("data-src") : imgElement.attr("src");
                    // 京东的图片链接通常省略了 https:，这里给它补上
                    if (img.startsWith("//")) {
                        img = "https:" + img;
                    }
                }

                // 【提取标题】: 寻找带有 title 属性的 span 或 div
                // 从你的 HTML 看: <span title="小米REDMI K90..." class="_text_1g56m_31">
                Element titleElement = el.select("span[title]").first();
                String title = titleElement != null ? titleElement.attr("title") : "";

                // 【提取价格】: 巧妙的方法——寻找包含 ¥ 符号的 <i> 标签，然后获取它父节点的文本
                // 你的 HTML: <span class="_price..."><i ...>¥</i>2081<span>.</span><span>65</span></span>
                Element priceSymbol = el.select("i:contains(¥)").first();
                String price = "";
                if (priceSymbol != null && priceSymbol.parent() != null) {
                    // 获取父节点所有文本，结果大概是 "¥2081.65"，我们把 ¥ 替换掉
                    price = priceSymbol.parent().text().replace("¥", "").trim();
                }

                // 只有解析到了标题和价格，才认为这是一个有效商品
                if (!title.isEmpty() && !price.isEmpty()) {
                    Content content = new Content();
                    content.setImg(img);
                    content.setPrice(price);
                    content.setTitle(title);
                    goodList.add(content);
                }
            } catch (Exception e) {
                // 捕获单条解析异常，防止一条报错导致整个循环崩溃
                System.out.println("某条商品解析失败，跳过: " + e.getMessage());
            }
        }
        return goodList;
    }
}
//
//public class HtmlParseUtil {
//
//    //测试数据
//    public static void main(String[] args) throws IOException, InterruptedException {
//        //获取请求
//        String url = "https://search.jd.com/Search?keyword=python";
//        // 解析网页 （Jsou返回的Document就是浏览器的Docuement对象）
//        Document document = Jsoup.parse(new URL(url), 30000);
//        //获取id，所有在js里面使用的方法在这里都可以使用
//        Element element = document.getElementById("J_goodsList");
//        //获取所有的li元素
//        Elements elements = element.getElementsByTag("li");
//        //用来计数
//        int c = 0;
//        //获取元素中的内容  ，这里的el就是每一个li标签
//        for (Element el : elements) {
//            c++;
//            //这里有一点要注意，直接attr使用src是爬不出来的，因为京东使用了img懒加载
//            String img = el.getElementsByTag("img").eq(0).attr("data-lazy-img");
//            //获取商品的价格，并且只获取第一个text文本内容
//            String price = el.getElementsByClass("p-price").eq(0).text();
//            String title = el.getElementsByClass("p-name").eq(0).text();
//            String shopName = el.getElementsByClass("p-shop").eq(0).text();
//
//            System.out.println("========================================");
//            System.out.println(img);
//            System.out.println(price);
//            System.out.println(title);
//            System.out.println(shopName);
//        }
//        System.out.println(c);
//    }
//}
