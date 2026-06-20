# 学习进度

## 当前阶段

第 2 天 / 共 30 天

## 今天目标

在第 1 天直线流程基础上，加入 Conditional Edge（分岔路口）：

```text
START -> intake -> audit -> route_by_audit_result
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

## 薄弱点

- Checkpointer 还没开始学
- Interrupt 还没开始学
- Reducer 还没开始学
- 需要继续练习：什么时候把判断留在 node 里，什么时候抽成 conditional edge

## 代码产出记录

| 天数 | 文件 | 验证状态 | 备注 |
|---|---|---|---|
| 第 1 天 | `src/audit_pipeline_poc/basic_graph.py` | 已本地运行 | 最小直线图 |
| 第 2 天 | `src/audit_pipeline_poc/conditional_graph.py` | 待本地运行 | 带分岔路口的审计流程 |
| 第 2 天 | `tests/test_conditional_graph.py` | 待本地运行 | 覆盖 passed / need_review / failed 分支 |

## 下一步计划

运行第 2 天程序，观察 `workflow_path` 字段，确认不同输入会走不同路线。

重点理解：

- audit 节点负责发现问题。
- route_by_audit_result 负责决定路线。
- review / delivery / error_report 分别负责不同分支上的后续处理。
