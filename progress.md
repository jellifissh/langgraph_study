# 学习进度

## 当前阶段

第 8 天 / 共 30 天

## 今天目标

学习 Interrupt 副作用安全：interrupt 恢复时节点会从头执行，所以 interrupt 前不能随便写外部系统。

Day 8 流程和 Day 7 基本一致，但新增 safe / unsafe 两种 human_review 写法：

```text
START -> intake -> normalize -> audit -> route_by_audit_result
                                      ├─ passed      -> delivery -> END
                                      ├─ need_review -> human_review -> route_after_human_review
                                      │                                  ├─ approved -> delivery -> END
                                      │                                  └─ rejected -> error_report -> END
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

## Checkpointer 与 Interrupt 的关系

- Checkpointer 负责存档。
- Interrupt 负责暂停。
- thread_id 负责找到同一个存档槽位。
- Command(resume=...) 负责把人类输入交回暂停处。

大白话：

```text
checkpointer = 游戏存档系统
interrupt = 暂停按钮
thread_id = 存档槽位
Command(resume=...) = 继续游戏时输入的选择
```

## Day 8 需要重点观察

- `unsafe_human_review()` 在 `interrupt(payload)` 前写外部日志。
- 恢复时节点从头执行，所以 unsafe 的前置外部日志会写两次。
- `safe_human_review()` 在 `interrupt(payload)` 前只准备 payload。
- safe 的外部日志放在 resume 之后，所以只写一次。
- `EXTERNAL_REVIEW_LOG` 是教学用的外部系统模拟器，不是真实生产存储。

## 副作用安全规则

interrupt 前可以做：

```text
纯计算
整理 payload
读取 State
构造给人看的复核材料
```

interrupt 前不要做：

```text
写数据库
发短信
发邮件
发 MQ
扣库存
调支付
任何不可重复执行的外部操作
```

## State 分区规则

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
- 幂等键还没开始专项练习
- 需要继续练习：interrupt 前的副作用必须谨慎，因为 resume 时节点会重新从头执行

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

## 下一步计划

运行第 8 天程序，对比 unsafe_report 和 safe_report。

重点理解：

- Interrupt 恢复时，节点会重新从头执行。
- interrupt 前只适合做纯计算。
- 外部副作用尽量放在 resume 之后。
- 如果副作用必须放在 interrupt 前，就必须设计幂等键。
