---
id: q_cpp_backend_project_132
doc_type: question
role: cpp_backend
category: project
subcategory: tcp_sticky_packet
question_type: project
difficulty: hard
tags: [cpp_backend, project, tcp_sticky_packet, network_os, os_network, cpp, protocol]
source_priority: high
applicable_features: [interview, scoring, practice, follow_up]
---
# 请结合项目讲讲 TCP 粘包拆包 的落地经验

## question
请结合一个真实项目，说明你在处理 TCP 粘包拆包 相关问题时的职责、方案、指标和复盘。

## reference_answer
项目题应把 TCP 粘包拆包 放回真实业务背景，讲清你本人职责、方案取舍、结果指标和后续优化。

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
