---
id: q_cpp_backend_principle_060
doc_type: question
role: cpp_backend
category: principle
subcategory: tcp_sticky_packet
question_type: principle
difficulty: medium
tags: [cpp_backend, principle, tcp_sticky_packet, network_os, os_network, cpp, protocol]
source_priority: high
applicable_features: [interview, scoring, practice, follow_up]
---
# TCP 粘包拆包 的底层原理怎么解释？

## question
请从机制角度解释 TCP 粘包拆包 为什么能工作，并说明它的关键约束。

## reference_answer
TCP 粘包拆包 是 C++ 后端 面试里常见的高频知识点，回答时应覆盖定义、机制、适用场景、边界条件和代价。 原理题需要把关键流程、收益来源、限制条件和代价讲清楚。

## key_points
- 先讲清 TCP 粘包拆包 的定义或问题背景
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
- TCP 粘包拆包 在你的项目里最难的取舍是什么？
- 如果结果不符合预期，你会怎样验证是不是 TCP 粘包拆包 引起的？
- TCP 粘包拆包 和 缓存击穿与热点治理 的边界应该怎么划分？
