---
id: q_cpp_backend_comparison_211
doc_type: question
role: cpp_backend
category: comparison
subcategory: rate_limiter
question_type: comparison
difficulty: medium
tags: [cpp_backend, comparison, rate_limiter, system_design, system_design, cpp, rate_limit]
source_priority: high
applicable_features: [interview, scoring, practice, follow_up]
---
# 限流与熔断 和 网关架构 应该怎么比较？

## question
请对比 限流与熔断 和 网关架构 的适用场景、优缺点以及你在项目里会如何选择。

## reference_answer
对比题要从目标、复杂度、维护成本、风险边界和团队成本几个维度回答，而不是只说哪个更好。

## key_points
- 先讲清 限流与熔断 的定义或问题背景
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
- 限流与熔断 在你的项目里最难的取舍是什么？
- 如果结果不符合预期，你会怎样验证是不是 限流与熔断 引起的？
- 限流与熔断 和 网关架构 的边界应该怎么划分？
