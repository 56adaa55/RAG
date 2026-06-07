package com.example.demo.controller;


import com.example.demo.EsDoc;

import com.example.demo.service.ContentService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.ResponseBody;

import java.io.IOException;
import java.util.List;
import java.util.Map;


//@RestController
@Controller

public class HelloController {

    @Autowired
    private ContentService contentService2;

    @GetMapping({"/","index"})
    public String index(){
        return "index";
    }
    @GetMapping("/jdsearch")
    public String hello2(Model model){
        return "jdsearch";
    }

    @GetMapping("/contentse")
    public String se(Model model){
        return "se";
    }

    @GetMapping("/searchAn/{aid}")
    public String parsese(Model model, @PathVariable("aid") String aid) throws IOException {

        System.out.println("【前端请求查询的问题ID】: " + aid);
        List<Map<String, Object>> list = contentService2.searchAnswer(aid);

        if (list == null || list.isEmpty()) {
            model.addAttribute("errorMsg", "未找到该问题或暂无相关答案");
            return "answer"; 
        }

        // 1. 问题的信息对于所有答案都是一样的，我们取第一个元素里的问题信息展示在头部
        model.addAttribute("qid", (String) list.get(0).get("qid"));
        model.addAttribute("qzh", (String) list.get(0).get("qzh"));
        model.addAttribute("qdomain", (String) list.get(0).get("qdomain"));

        // 2. 把【整个包含多个答案的 List】传给前端，让前端去循环遍历！
        model.addAttribute("answerList", list);

        return "answer";
    }
    @GetMapping("/hello")
    public String hello(Model model){
        model.addAttribute("hello","hello welcome");
        return "test";
    }

    @GetMapping("/hello1")
    @ResponseBody
    public String handle01() throws IOException {
        String str;
        str=EsDoc.searchDoc();
        return str+"\nHello, Spring Boot2!";

    }

    @GetMapping("/getStr")
    @ResponseBody
    public String getStr() throws IOException {
        String str;
        return "\nHello, Spring Boot2!";
    }
}