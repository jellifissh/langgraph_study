# 学习进度

## 当前阶段

第 5 天 / 共 30 天

## 今天目标

学习 Reducer：账本字段被多个节点更新时，到底是覆盖，还是追加。

Day 5 新流程和 Day 4 基本一致，但把部分 list 字段改成 reducer 累积：

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

## Reducer 大白话

默认更新规则：

```text
新值覆盖旧值
```

带 reducer 的更新规则：

```text
旧值 + 新值 合并成最终值
```

本项目 Day 5 使用：

```python
Annotated[list[str], add]
```

用于累积：

- `workflow_path`
- `audit_errors`
- `warnings`
- `audit_events`

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

- Checkpointer 还没开始学
- Interrupt 还没开始学
- 需要继续练习：哪些字段应该覆盖，哪些字段应该追加
- 需要继续练习：reducer 适合审计事件流水，但不适合所有字段

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

## 下一步计划

运行第 5 天程序，观察 `workflow_path` 和 `audit_events` 如何由多个节点逐步追加。

重点理解：

- 不带 reducer：同一个字段更新时默认覆盖。
- 带 reducer：同一个字段可以按规则合并。
- reducer 适合用于事件流水、路线记录、错误列表、warning 列表。
- `audit_status` 这种单一结论不应该用 reducer，应该覆盖成最新结论。
