## 1. Agent Memory.pdf
**标题:** Agent Memory: Characterization and System Implications of Stateful Long-Horizon Workloads
**简介:** 
本文探讨了在长时间跨度的任务中，LLM智能体如何管理和维持长期记忆。研究者首次对智能体记忆系统进行了系统级的特性分析，提出了一个系统导向的分类法。通过构建阶段感知的分析工具，论文评估了十个代表性系统的构建、检索和生成成本，并提出了10条关于智能体记忆系统设计的优化建议，涵盖调度、延迟权衡和队列管理等方面。

## 2. Benchmark Everything Everywhere All at Once.pdf
**标题:** Benchmark Everything Everywhere All at Once
**简介:** 
为了解决当前LLM和多模态模型评估基准构建耗时费力且容易饱和的问题，本文介绍了一个名为 **Benchmark Agent** 的全自动智能体系统。该系统能够自主完成从用户需求分析、子任务设计到数据标注和质量控制的完整基准测试构建流程。研究团队利用该系统生成了15个高质量的基准测试，涵盖文本理解、多模态理解和特定领域推理。

## 3. DeepSeek_OCR2_paper.pdf
**标题:** DeepSeek-OCR 2: Visual Causal Flow
**简介:** 
本文提出了 **DeepSeek-OCR 2**，并引入了一种新颖的视觉编码器 **DeepEncoder V2**。传统的视觉语言模型通常以固定的光栅扫描顺序处理视觉Token，而该研究借鉴人类视觉认知的灵活性，使编码器能够根据图像的语义和因果逻辑动态重排视觉Token。这种基于“因果视觉流”的架构在复杂文档阅读和OCR任务中表现出了显著的性能提升。

## 4. Goedel-Architect.pdf
**标题:** Goedel-Architect: Streamlining Formal Theorem Proving with Blueprint Generation and Refinement
**简介:** 
本文介绍了一个名为 **Goedel-Architect** 的智能体框架，专门用于Lean 4语言中的形式化定理证明。该框架的核心思想是“蓝图生成与细化”：它首先生成一个包含定义和引理依赖关系的全局蓝图，然后并行验证各个引理。失败的引理会触发全局蓝图的修正。基于DeepSeek模型，该框架在MiniF2F和PutnamBench等高难度数学基准测试中达到了开源管道的最先进水平。

## 5. Humans ALMANAC.pdf
**标题:** Humans’ ALMANAC: A Human Collaboration Dataset of Action-Level Mental Model ANnotations for Agent Collaboration
**简介:** 
随着LLM智能体越来越具备人类协作者的角色，本文旨在弥补当前缺乏真实人类协作及心智模型数据的空白。研究者提出了 **ALMANAC** 数据集，其中包含了基于经典“地图任务 (Map Task)”的近3000个协作动作，并附带了动作级别的心智模型注释（如自我推理、感知到的伙伴意图和团队目标）。该数据集为训练和评估智能体理解人类协作意图的能力提供了重要基准。
