---
id: q_web_frontend_design_coding_184
doc_type: question
role: web_frontend
category: design_coding
subcategory: lcp
question_type: design_coding
difficulty: hard
tags: [web_frontend, design_coding, lcp, engineering_perf_security, network_performance, web, lcp]
source_priority: high
applicable_features: [interview, scoring, practice, follow_up]
---
# 围绕 LCP 设计一个可落地方案

## question
如果让你设计一个和 LCP 强相关的模块，请说明核心接口、状态流转、监控指标和异常处理。

## reference_answer
LCP 是 Web 前端 面试里常见的高频知识点，回答时应覆盖定义、机制、适用场景、边界条件和代价。 设计题要强调职责边界、关键数据结构、失败路径和可观测性。

## key_points
- 先讲清 LCP 的定义或问题背景
- 再说明机制、限制和真实场景
- 补充项目证据、指标或验证方式
- 明确边界条件与风险点

## common_mistakes
- 只背结论，不解释为什么
- 不说明适用边界和代价
- 无法给出真实项目或验证证据

## scoring_rubric
- 90+：原理、取舍、指标和项目复盘都能讲清
- 75+：原理与场景清楚，但细节略少
- 60+：只会背概念，没有真实落地证据
- 40-：概念混乱或无法自洽

## follow_up_questions
- LCP 在你的项目里最难的取舍是什么？
- 如果结果不符合预期，你会怎样验证是不是 LCP 引起的？
- LCP 和 组件库 的边界应该怎么划分？
