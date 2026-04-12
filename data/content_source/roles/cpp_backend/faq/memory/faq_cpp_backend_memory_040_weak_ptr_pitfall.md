---
id: faq_cpp_backend_memory_040
doc_type: knowledge
role: cpp_backend
category: memory
subcategory: weak_ptr
level: intermediate
tags: [cpp_backend, memory, weak_ptr, cpp_language, pitfall, cpp, weak_ptr]
applicable_features: [search, interview, follow_up]
---
# weak_ptr：误区与排障

## question
weak_ptr 最容易出现哪些误区或线上问题？

## answer
weak_ptr 是 C++ 后端 面试里常见的高频知识点，回答时应覆盖定义、机制、适用场景、边界条件和代价。 回答时要强调定义、机制、场景和边界，而不是只背结论。

## extended_explanation
围绕 weak_ptr 继续展开时，应补充真实项目中的收益、代价、监控方式和不适用场景。

## follow_up_questions
- weak_ptr 和 智能指针 的边界该怎么划分？
- 你在项目里如何验证 weak_ptr 的效果？
