package com.example.demo.utils;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONArray;
import com.alibaba.fastjson.JSONObject;
import com.alibaba.fastjson.JSONObject;
import com.example.demo.pojo.Answer;
import com.example.demo.pojo.Question;
import com.example.demo.pojo.Content;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.springframework.stereotype.Component;

import java.io.*;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;


@Component


public class JsonParseUtil {
//    public static void main(String[] args) throws IOException {
//        String file_path="D:/insuranceqa_data/corpus/pool/trainnew.json";
//        List<Question> ql=new JsonParseUtil().parseJson(file_path);
////        System.out.println(ql.size());
//    }

    public List<Question> parseJson(String json_file_path) throws IOException {
        File jsonFile = new File(json_file_path);
        String jsonStr="";
        List<Question> questionList=null;




        try {

//            BufferedReader in = new BufferedReader(new InputStreamReader(
//                    new FileInputStream(jsonFile), "UTF-8"));
//
//            StringBuffer bs = new StringBuffer();
//            String l = null;
//            while((l=in.readLine())!=null){
//                bs.append(l).append("/n");
//            }
            Reader reader = new InputStreamReader(new FileInputStream(jsonFile),"utf-8");
            int ch = 0;
            StringBuffer sb = new StringBuffer();
            while ((ch = reader.read()) != -1) {
                sb.append((char) ch);
            }

            reader.close();
            jsonStr = sb.toString();
        } catch (IOException e) {
            e.printStackTrace();
        }



//        System.out.println(jsonStr.substring(0,100));
        JSONArray jsonArr = JSON.parseArray(jsonStr);
//        System.out.println(jsonArr.toString().substring(0,100));
        //ArrayList<Question> qList = new ArrayList<>();
        questionList = jsonArr.toJavaList(Question.class);//转化为特定的List
//        System.out.println(questionList.size());

//       ---------------采用jsonobject keyset方法获得list
//        //转json对象
//        JSONObject ids = (JSONObject)JSONObject.parse(jsonStr);
//        //Set<String> stringSet=ids.keySet();
//        Set<String> stringSet = ids.keySet();
//        //获取主要数据
//        String keystr="";
//        for (String str : stringSet) {
//            keystr=str;-
//            JSONObject ob=ids.getJSONObject(keystr);
//            System.out.println(ob.get("zh"));
//
//        }

        return questionList;
    }



    public List<Answer> parseAnJson(String json_file_path) throws IOException {
        File jsonFile = new File(json_file_path);
        String jsonStr="";
        List<Answer> answerList=null;


        try {

            Reader reader = new InputStreamReader(new FileInputStream(jsonFile),"utf-8");
            int ch = 0;
            StringBuffer sb = new StringBuffer();
            while ((ch = reader.read()) != -1) {
                sb.append((char) ch);
            }

            reader.close();
            jsonStr = sb.toString();
        } catch (IOException e) {
            e.printStackTrace();
        }


        JSONArray jsonArr = JSON.parseArray(jsonStr);
        answerList = jsonArr.toJavaList(Answer.class);//转化为特定的List

        return answerList;
    }


    public List<Content> parseJDJson(String json_file_path) throws IOException {
        File jsonFile = new File(json_file_path);
        String jsonStr="";
        List<Content> goodsList=null;

        try {

            Reader reader = new InputStreamReader(new FileInputStream(jsonFile),"utf-8");
            int ch = 0;
            StringBuffer sb = new StringBuffer();
            while ((ch = reader.read()) != -1) {
                sb.append((char) ch);
            }

            reader.close();
            jsonStr = sb.toString();
        } catch (IOException e) {
            e.printStackTrace();
        }

        JSONArray jsonArr = JSON.parseArray(jsonStr);

        goodsList = jsonArr.toJavaList(Content.class);//转化为特定的List


        return goodsList;
    }

}

/*
public class HtmlParseUtil {

    //测试数据
    public static void main(String[] args) throws IOException, InterruptedException {
        //获取请求
        String url = "https://search.jd.com/Search?keyword=python";
        // 解析网页 （Jsou返回的Document就是浏览器的Docuement对象）
        Document document = Jsoup.parse(new URL(url), 30000);
        //获取id，所有在js里面使用的方法在这里都可以使用
        Element element = document.getElementById("J_goodsList");
        //获取所有的li元素
        Elements elements = element.getElementsByTag("li");
        //用来计数
        int c = 0;
        //获取元素中的内容  ，这里的el就是每一个li标签
        for (Element el : elements) {
            c++;
            //这里有一点要注意，直接attr使用src是爬不出来的，因为京东使用了img懒加载
            String img = el.getElementsByTag("img").eq(0).attr("data-lazy-img");
            //获取商品的价格，并且只获取第一个text文本内容
            String price = el.getElementsByClass("p-price").eq(0).text();
            String title = el.getElementsByClass("p-name").eq(0).text();
            String shopName = el.getElementsByClass("p-shop").eq(0).text();

            System.out.println("========================================");
            System.out.println(img);
            System.out.println(price);
            System.out.println(title);
            System.out.println(shopName);
        }
        System.out.println(c);
    }
}*/
