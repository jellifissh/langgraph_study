# 学习进度

## 当前阶段

第 13 天 / 共 30 天

## 今天目标

学习 Agent Loop / ReAct-style Tool Loop：模型不再只规划一次，而是每一轮看当前状态和工具结果，决定下一步继续调工具还是结束。

```text
START -> intake -> agent_decide -> route_after_agent_decide
                         ├─ tool  -> execute_agent_tool -> agent_decide -> ...
                         └─ final -> finalize_agent_answer -> route_by_audit_status
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
- Agent Loop = decide -> act -> observe -> decide 的多轮循环

## Day 13 Agent Loop 大白话

Day 12：

```text
LLM 一次性生成 tool_calls
```

Day 13：

```text
LLM 每轮只决定下一步
如果需要证据，就调用一个工具
工具结果回来后，再让 LLM 决定下一步
证据够了，就 final
```

这就是：

```text
decide -> execute tool -> observe -> decide -> execute tool -> observe -> final
```

## Day 13 需要重点观察

- `AgentAction` 有两类：`tool` 和 `final`。
- `agent_decide` 负责决定下一步。
- `execute_agent_tool` 只执行当前一个工具。
- 工具执行后会回到 `agent_decide`，形成循环。
- `max_agent_steps` 防止无限循环。
- 没有 DeepSeek 环境变量时，会走 rule fallback loop。

## Agent 主线位置

Day 13 对应 Agent 系统里的核心循环：

```text
用户目标
  ↓
LLM / Rule Agent Decide
  ↓
Tool Executor
  ↓
Observation / Tool Result
  ↓
LLM / Rule Agent Decide
  ↓
Final Answer
```

这比 Day 12 更接近真正 Agent：不是一次规划，而是多轮观察和决策。

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
| 第 13 天 | `src/audit_pipeline_poc/agent_loop_graph.py` | 待本地运行 | 多轮 agent decide / tool / observe 循环 |
| 第 13 天 | `tests/test_agent_loop_graph.py` | 待本地运行 | 覆盖 action 解析、fake LLM loop、rule fallback、step limit |

## 下一步计划

运行第 13 天程序，重点观察：

- `agent_steps`
- `current_action`
- `tool_results`
- `final_answer`
- `workflow_path`

重点理解：

- Agent loop 不是一次性规划，而是多轮决策。
- 每轮只做一个 action。
- 工具结果是下一轮决策的观察输入。
- 需要 `max_agent_steps` 兜住死循环。
- 真实 LLM 负责 decide，代码仍然负责工具执行和状态流转。
