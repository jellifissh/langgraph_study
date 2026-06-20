# 学习进度

## 当前阶段

第 6 天 / 共 30 天

## 今天目标

学习 Checkpointer：让图执行过程可以存档、查询最新状态、查询历史状态。

Day 6 流程和 Day 5 基本一致，但 compile 时加入 checkpointer：

```text
START -> intake -> normalize -> audit -> route_by_audit_result
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
- thread_id = 存档槽位 / 任务编号

## Checkpointer 大白话

不带 checkpointer：

```text
流程跑完就只剩最终结果
```

带 checkpointer：

```text
流程每一步都会留下 State 快照
```

本项目 Day 6 使用：

```python
from langgraph.checkpoint.memory import InMemorySaver

graph.compile(checkpointer=InMemorySaver())
```

## Day 6 需要重点观察

- `thread_id`：区分不同任务的存档槽位。
- `app.get_state(config)`：读取某个 thread 的最新 State。
- `app.get_state_history(config)`：读取某个 thread 的历史 State 快照。
- `history_length`：观察一次图运行大概保存了多少个 checkpoint。
- `snapshot.next`：如果为空，说明图已经跑完；如果不为空，说明还有节点待执行。

## State 分区规则

- `raw_fields`：原始输入区，外部传来的字段，可能类型混乱或缺字段。
- `normalized_fields`：标准化字段区，后续节点优先读取这里。
- `audit_errors`：硬错误，会让流程进入 failed。
- `warnings`：软风险，可能让流程进入 need_review。
- `audit_events`：审计事件流水，不是最终业务结论。
- `audit_status`：分岔路口使用的状态结论。
- `review_note`：人工复核或模拟复核说明。
- `delivery_message`：最终交付表达。
- `workflow_path`：调试路线记录。

## 薄弱点

- Interrupt 还没开始学
- Store 还没开始学
- Time travel 还没开始学
- 需要继续练习：checkpointer 是短期线程状态，store / 数据库才适合长期跨任务记忆

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

## 下一步计划

运行第 6 天程序，观察 `latest` 和 `history` 的区别。

重点理解：

- Checkpointer 不是普通日志，它保存的是图执行过程中的 State 快照。
- 必须传 `thread_id`，否则存档器不知道你要把状态放到哪个任务槽位里。
- get_state 看最新存档。
- get_state_history 看历史存档。
- 这为后面的 Interrupt / 人工复核恢复执行打基础。
