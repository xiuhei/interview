---
id: q_cpp_backend_troubleshooting_253
doc_type: question
role: cpp_backend
category: troubleshooting
subcategory: lambda_capture
question_type: troubleshooting
difficulty: medium
tags: [cpp_backend, troubleshooting, lambda_capture, language, cpp_language, cpp, lambda]
source_priority: high
applicable_features: [interview, scoring, practice, follow_up]
---
# 如果 Lambda 捕获 出问题，你会怎么排查？

## question
如果线上出现和 Lambda 捕获 相关的故障，请给出你的排查顺序、证据来源和止血策略。

## reference_answer
Lambda 捕获 是 C++ 后端 面试里常见的高频知识点，回答时应覆盖定义、机制、适用场景、边界条件和代价。 排障题的核心是分层定性、建立证据链、快速止血，再回到根因和长期治理。

## key_points
- 先讲清 Lambda 捕获 的定义或问题背景
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
- Lambda 捕获 在你的项目里最难的取舍是什么？
- 如果结果不符合预期，你会怎样验证是不是 Lambda 捕获 引起的？
- Lambda 捕获 和 vector 扩容 的边界应该怎么划分？
