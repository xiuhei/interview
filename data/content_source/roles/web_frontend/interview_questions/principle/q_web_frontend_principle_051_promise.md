---
id: q_web_frontend_principle_051
doc_type: question
role: web_frontend
category: principle
subcategory: promise
question_type: principle
difficulty: hard
tags: [web_frontend, principle, promise, async_event_loop, frontend_foundation, web, promise]
source_priority: high
applicable_features: [interview, scoring, practice, follow_up]
---
# Promise 的底层原理怎么解释？

## question
请从机制角度解释 Promise 为什么能工作，并说明它的关键约束。

## reference_answer
Promise 是 Web 前端 面试里常见的高频知识点，回答时应覆盖定义、机制、适用场景、边界条件和代价。 原理题需要把关键流程、收益来源、限制条件和代价讲清楚。

## key_points
- 先讲清 Promise 的定义或问题背景
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
- Promise 在你的项目里最难的取舍是什么？
- 如果结果不符合预期，你会怎样验证是不是 Promise 引起的？
- Promise 和 浏览器缓存 的边界应该怎么划分？
