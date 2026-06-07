package com.example.demo.pojo;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class Question{
    private String qid;
    private String qzh;
    private String qen;

    private String qdomain;
    private String qanswers;
    private String qnegatives;

    //可以自行添加属性
}
