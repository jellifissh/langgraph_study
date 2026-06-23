# 学习进度

## 当前阶段

第 12 天 / 共 30 天

## 今天目标

学习 LLM Planner：把 Day 11 的手写 `plan_tool_calls()` 换成模型规划工具调用。模型配置从本机环境变量读取 DeepSeek。

```text
START -> intake -> llm_plan_tool_calls -> execute_tools -> synthesize_audit -> route_by_audit_status
                                                                            ├─ passed      -> delivery -> END
                                                                            ├─ need_review -> review -> delivery -> END
                                                                            └─ failed      -> error_report -> END
```

## 已掌握概念

- State = 账本
- Node = 点 / 工位
- Edge = 线 / 路
- Graph = 流程地图
- Conditional Edge = 分岔路口
- route 函数 = 只负责决定下一站去哪，不负责做业务处理
- Mermaid = 图的文本表示
- workflow_path = 单次运行的真实路线记录
- State Schema = 账本字段设计
- Reducer = 字段更新规则
- Checkpointer = 图执行状态存档器
- thread_id = 某个具体任务的存档槽位 / 任务编号
- Interrupt = 节点内部的暂停点
- Command(resume=...) = 恢复暂停节点时传回的人类输入
- Side effect = 外部副作用，例如写数据库、发短信、发 MQ、调支付接口
- Idempotency Key = 幂等键，同一业务动作的稳定唯一标识
- Outbox = 待发送事件表 / 待发送消息箱
- Dispatcher = 专门发送 outbox 事件的后台工人
- Tool Call = 一次工具调用请求，包括工具名和参数
- Tool Registry = 工具注册表，负责把工具名映射到真实函数
- Tool Executor = 工具执行节点，负责执行工具并返回结果
- LLM Planner = 用模型根据任务和工具列表生成 tool_calls

## Day 12 LLM Planner 大白话

Day 11：

```text
规则 planner 手写 tool_calls
```

Day 12：

```text
把 company / revenue / net_profit / available_tools 给模型
模型返回 JSON tool_calls
executor 按 tool_calls 执行工具
```

LLM Planner 不是让模型随便幻想工具，而是让模型在已有工具列表里选择。

## DeepSeek 环境变量

本项目读取：

```text
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL
DEEPSEEK_MODEL
```

代码不会写死 key。
测试使用 FakeClient，不会真的请求 DeepSeek。
本地运行 demo 时，如果环境变量存在会用 DeepSeek；如果没有，会回退到 rule planner。

## Day 12 需要重点观察

- `DeepSeekChatClient.from_env()` 从环境变量读取模型配置。
- `build_planner_messages()` 把可用工具列表和输出格式发给模型。
- `parse_tool_calls_from_llm_response()` 解析模型返回的 JSON。
- `make_llm_plan_tool_calls_node()` 支持注入 FakeClient，测试不依赖真实 API。
- LLM 失败时可以回退到 rule planner。

## Agent 主线位置

Day 12 对应 Agent 系统里的这一段：

```text
用户目标
  ↓
LLM Planner 根据目标和工具列表生成 tool_calls
  ↓
Tool Executor 执行工具
  ↓
Synthesizer 综合工具结果
  ↓
Graph 根据结论分流
```

这是比 Day 11 更接近真实 Agent 的版本。

## 代码产出记录

| 天数 | 文件 | 验证状态 | 备注 |
|---|---|---|---|
| 第 1 天 | `src/audit_pipeline_poc/basic_graph.py` | 已本地运行 | 最小直线图 |
| 第 2 天 | `src/audit_pipeline_poc/conditional_graph.py` | 已本地运行 | 带分岔路口的审计流程 |
| 第 3 天 | `src/audit_pipeline_poc/visualize_graphs.py` | 待本地运行 | 导出 Mermaid 图 |
| 第 4 天 | `src/audit_pipeline_poc/state_schema_graph.py` | 待本地运行 | 结构化 State 账本 |
| 第 4 天 | `tests/test_state_schema_graph.py` | 待本地运行 | 覆盖结构化 State 的 passed / review / failed |
| 第 5 天 | `src/audit_pipeline_poc/reducer_graph.py` | 待本地运行 | 用 reducer 累积 list 字段 |
| 第 5 天 | `tests/test_reducer_graph.py` | 待本地运行 | 覆盖 path、warnings、errors、events 的累积行为 |
| 第 6 天 | `src/audit_pipeline_poc/checkpointer_graph.py` | 待本地运行 | 用 checkpointer 保存 State 快照 |
| 第 6 天 | `tests/test_checkpointer_graph.py` | 待本地运行 | 覆盖最新状态、历史状态、thread 隔离 |
| 第 7 天 | `src/audit_pipeline_poc/interrupt_graph.py` | 待本地运行 | 用 interrupt 暂停人工复核 |
| 第 7 天 | `tests/test_interrupt_graph.py` | 待本地运行 | 覆盖暂停、approve 恢复、reject 恢复、非 review 不暂停 |
| 第 8 天 | `src/audit_pipeline_poc/interrupt_safety_graph.py` | 待本地运行 | 演示 interrupt 前副作用重复执行风险 |
| 第 8 天 | `tests/test_interrupt_safety_graph.py` | 待本地运行 | 覆盖 unsafe 重复写、safe 单次写、错误 thread resume |
| 第 9 天 | `src/audit_pipeline_poc/idempotency_graph.py` | 待本地运行 | interrupt 前外部写入的幂等键保护 |
| 第 9 天 | `tests/test_idempotency_graph.py` | 待本地运行 | 覆盖稳定 key、只创建一次、approve/reject 更新同一审批单 |
| 第 10 天 | `src/audit_pipeline_poc/outbox_graph.py` | 待本地运行 | 审批结果写 outbox，不直接发送通知 |
| 第 10 天 | `tests/test_outbox_graph.py` | 待本地运行 | 覆盖事件登记、pending/sent、dispatcher 不重复发送 |
| 第 11 天 | `src/audit_pipeline_poc/tool_calling_graph.py` | 待本地运行 | 工具规划、工具执行、工具结果综合 |
| 第 11 天 | `tests/test_tool_calling_graph.py` | 待本地运行 | 覆盖工具函数、工具执行错误、passed/review/failed 路径 |
| 第 12 天 | `src/audit_pipeline_poc/llm_planner_graph.py` | 待本地运行 | DeepSeek LLM planner 生成 tool_calls |
| 第 12 天 | `tests/test_llm_planner_graph.py` | 待本地运行 | 覆盖 fake client、JSON 解析、未知工具、fallback、env 读取 |

## 下一步计划

运行第 12 天程序，重点观察：

- `planner_mode`
- `llm_prompt`
- `llm_response`
- `tool_calls`
- `tool_results`

重点理解：

- LLM Planner 的输出不是自然语言，而是结构化 tool_calls。
- 模型只能从已有工具列表里选，不能乱造工具。
- Tool Executor 仍然是确定性执行器。
- 测试里不要真的请求模型，要用 FakeClient。
