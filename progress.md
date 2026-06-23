# 学习进度

## 当前阶段

第 9 天 / 共 30 天

## 今天目标

学习幂等键 Idempotency Key：当 interrupt 前必须写外部系统时，用稳定唯一 key 防止重复创建。

Day 9 流程和 Day 8 基本一致，但 human_review 在 interrupt 前创建“待审批单”，并用 review_request_id 防重复：

```text
START -> intake -> normalize -> audit -> route_by_audit_result
                                      ├─ passed      -> delivery -> END
                                      ├─ need_review -> human_review_with_idempotency -> route_after_human_review
                                      │                                                   ├─ approved -> delivery -> END
                                      │                                                   └─ rejected -> error_report -> END
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

## Day 9 幂等键大白话

没有幂等键：

```text
节点重跑一次，外部系统可能创建两条审批单
```

有幂等键：

```text
节点可以重跑，但同一个 review_request_id 只创建一条审批单
```

本项目 Day 9 使用：

```python
review_request_id = f"{task_id}:human_review:round1"
```

这个 key 的含义是：

```text
某个任务 + human_review 节点 + 第 1 轮复核
```

## Day 9 需要重点观察

- `create_review_request_once(state)` 在 `interrupt(payload)` 前执行。
- resume 时 human_review 节点会从头执行，所以它会被调用两次。
- 第一次：创建审批单。
- 第二次：发现同一个 review_request_id 已存在，跳过重复创建。
- `EXTERNAL_REVIEW_REQUESTS` 最终只有一条审批单。
- `EXTERNAL_CALL_LOG` 会显示两次尝试，但只有一次真正 created。

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

interrupt 前不要裸写：

```text
没有幂等键的数据库 insert
没有去重的短信 / 邮件 / MQ
没有唯一约束的审批单创建
没有请求编号的支付 / 扣库存
```

## State 分区规则

- `task_id`：某次审计任务的业务 ID。
- `review_request_id`：人工复核请求的幂等键。
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
- 数据库唯一索引还没接真实实现
- outbox 模式还没开始学

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

## 下一步计划

运行第 9 天程序，观察 `external_call_log` 和 `external_review_requests` 的区别。

重点理解：

- 幂等不是“不执行两次代码”。
- 幂等是“代码可以被调用多次，但外部业务结果只发生一次”。
- key 必须稳定，不能用随机数。
- 真生产里要靠数据库唯一索引 / 去重逻辑 / 事务边界兜住。
