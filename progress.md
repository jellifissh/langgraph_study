# 学习进度

## 当前阶段

第 10 天 / 共 30 天

## 今天目标

学习 Outbox 模式：业务流程不要直接发外部通知，而是先登记 outbox 事件，再由 dispatcher 统一发送。

Day 10 流程和 Day 9 基本一致，但 human_review 恢复后不直接发通知，而是写入 outbox event：

```text
START -> intake -> normalize -> audit -> route_by_audit_result
                                      ├─ passed      -> delivery -> END
                                      ├─ need_review -> human_review_with_outbox -> route_after_human_review
                                      │                                             ├─ approved -> delivery -> END
                                      │                                             └─ rejected -> error_report -> END
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

## Day 10 Outbox 大白话

直接发送：

```text
流程里直接发短信 / MQ / Webhook
```

风险：

```text
通知发出去了，但业务状态没落稳
流程重试时通知又发一遍
发送失败后不知道该怎么补发
```

Outbox：

```text
流程只写一条 outbox event
后台 dispatcher 再发送 pending event
发送成功后标记 sent
```

## Day 10 需要重点观察

- `enqueue_outbox_event_once(...)` 只登记事件，不真正发送。
- `OUTBOX_EVENTS` 是待发送事件存储。
- `SENT_MESSAGES` 是真正发出去的消息。
- graph 结束后，如果不跑 dispatcher，消息不会发出去。
- `dispatch_outbox_events()` 只发送 pending 事件。
- 同一个 dispatcher 跑两次，第二次不会重复发送 sent 事件。

## Outbox 与幂等键的关系

- 幂等键保护“不要重复创建同一个业务对象”。
- Outbox 保护“不要在业务流程里直接裸发外部通知”。
- Outbox event 自己也需要稳定 event_id，防止重复登记事件。

本项目 Day 10 使用：

```python
event_id = f"{review_request_id}:decision:{decision}"
```

## 副作用安全规则

interrupt 前可以做：

```text
纯计算
整理 payload
读取 State
构造给人看的复核材料
```

interrupt 前如果必须做外部写入：

```text
必须有幂等键
必须有唯一约束 / 去重逻辑
最好有事务边界 / outbox / 状态机保护
```

外部通知发送：

```text
不要在 graph 节点里直接发送
优先写 outbox event
再由 dispatcher 发送
```

## State 分区规则

- `task_id`：某次审计任务的业务 ID。
- `review_request_id`：人工复核请求的幂等键。
- `outbox_event_id`：审批结果通知事件的幂等键。
- `raw_fields`：原始输入区，外部传来的字段，可能类型混乱或缺字段。
- `normalized_fields`：标准化字段区，后续节点优先读取这里。
- `audit_errors`：硬错误，会让流程进入 failed。
- `warnings`：软风险，可能让流程进入 need_review。
- `audit_events`：审计事件流水，不是最终业务结论。
- `audit_status`：分岔路口使用的状态结论。
- `review_decision`：人工复核决定，approved / rejected。
- `review_note`：人工复核说明。
- `delivery_message`：最终交付表达。
- `workflow_path`：调试路线记录。

## 薄弱点

- Store 还没开始学
- Time travel 还没开始学
- 真实 UI 表单还没接入
- 真实数据库事务 / 唯一索引还没接入
- outbox dispatcher 还只是同步函数模拟

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

## 下一步计划

运行第 10 天程序，观察 `outbox_events` 和 `sent_messages` 的区别。

重点理解：

- Outbox 不是消息本身，而是“待发送事件记录”。
- Graph 只负责写 outbox，不直接裸发外部通知。
- Dispatcher 专门发送 pending 事件。
- 发送成功后标记 sent。
- Dispatcher 重跑不会重复发送 sent 事件。
