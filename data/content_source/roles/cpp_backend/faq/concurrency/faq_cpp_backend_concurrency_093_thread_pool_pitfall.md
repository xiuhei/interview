---
id: faq_cpp_backend_concurrency_093
doc_type: knowledge
role: cpp_backend
category: concurrency
subcategory: thread_pool
level: advanced
tags: [cpp_backend, concurrency, thread_pool, system_design, pitfall, cpp, thread_pool]
applicable_features: [search, interview, follow_up]
---
# 线程池：误区与排障

## question
线程池 最容易出现哪些误区或线上问题？

## answer
线程池 是 C++ 后端 面试里常见的高频知识点，回答时应覆盖定义、机制、适用场景、边界条件和代价。 回答时要强调定义、机制、场景和边界，而不是只背结论。

## extended_explanation
围绕 线程池 继续展开时，应补充真实项目中的收益、代价、监控方式和不适用场景。

## follow_up_questions
- 线程池 和 Lambda 捕获 的边界该怎么划分？
- 你在项目里如何验证 线程池 的效果？
