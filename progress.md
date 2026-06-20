# 学习进度

## 当前阶段

第 4 天 / 共 30 天

## 今天目标

学习 State Schema 设计：账本不是字段越多越好，而是要分区清楚。

Day 4 新流程：

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

## State 分区规则

- `raw_fields`：原始输入区，外部传来的字段，可能类型混乱或缺字段。
- `normalized_fields`：标准化字段区，后续节点优先读取这里。
- `audit_errors`：硬错误，会让流程进入 failed。
- `warnings`：软风险，可能让流程进入 need_review。
- `audit_status`：分岔路口使用的状态结论。
- `review_note`：人工复核或模拟复核说明。
- `delivery_message`：最终交付表达。
- `workflow_path`：调试路线记录。

## 薄弱点

- Checkpointer 还没开始学
- Interrupt 还没开始学
- Reducer 还没开始学
- 需要继续练习：哪些字段应该进 State，哪些只是节点内部临时变量

## 代码产出记录

| 天数 | 文件 | 验证状态 | 备注 |
|---|---|---|---|
| 第 1 天 | `src/audit_pipeline_poc/basic_graph.py` | 已本地运行 | 最小直线图 |
| 第 2 天 | `src/audit_pipeline_poc/conditional_graph.py` | 已本地运行 | 带分岔路口的审计流程 |
| 第 3 天 | `src/audit_pipeline_poc/visualize_graphs.py` | 待本地运行 | 导出 Mermaid 图 |
| 第 4 天 | `src/audit_pipeline_poc/state_schema_graph.py` | 待本地运行 | 结构化 State 账本 |
| 第 4 天 | `tests/test_state_schema_graph.py` | 待本地运行 | 覆盖结构化 State 的 passed / review / failed |

## 下一步计划

运行第 4 天程序，观察 `raw_fields`、`normalized_fields`、`audit_errors`、`warnings` 的区别。

重点理解：

- raw_fields 是原材料，不保证干净。
- normalized_fields 是清洗后的字段，后续节点应该优先读这里。
- audit_errors 是硬错误。
- warnings 是软风险。
- State Schema 是 Agent 工程里的账本设计，不是随便塞 dict。
