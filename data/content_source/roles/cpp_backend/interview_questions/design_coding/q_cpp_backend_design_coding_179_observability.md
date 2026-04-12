---
id: q_cpp_backend_design_coding_179
doc_type: question
role: cpp_backend
category: design_coding
subcategory: observability
question_type: design_coding
difficulty: hard
tags: [cpp_backend, design_coding, observability, system_design, performance, cpp, observability]
source_priority: high
applicable_features: [interview, scoring, practice, follow_up]
---
# 围绕 可观测性 设计一个可落地方案

## question
如果让你设计一个和 可观测性 强相关的模块，请说明核心接口、状态流转、监控指标和异常处理。

## reference_answer
可观测性 是 C++ 后端 面试里常见的高频知识点，回答时应覆盖定义、机制、适用场景、边界条件和代价。 设计题要强调职责边界、关键数据结构、失败路径和可观测性。

## key_points
- 先讲清 可观测性 的定义或问题背景
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
- 可观测性 在你的项目里最难的取舍是什么？
- 如果结果不符合预期，你会怎样验证是不是 可观测性 引起的？
- 可观测性 和 RAII 的边界应该怎么划分？
