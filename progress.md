# 学习进度

## 当前阶段

第 1 天 / 共 30 天

## 今天目标

跑通最小 LangGraph 审计流程：

```text
START -> intake -> audit -> delivery -> END
```

## 已掌握概念

- State = 账本
- Node = 点 / 工位
- Edge = 线 / 路
- Graph = 流程地图

## 薄弱点

- Conditional Edge 还没开始学
- Checkpointer 还没开始学
- Interrupt 还没开始学

## 代码产出记录

| 天数 | 文件 | 验证状态 | 备注 |
|---|---|---|---|
| 第 1 天 | `src/audit_pipeline_poc/basic_graph.py` | 待本地运行 | 最小直线图 |

## 下一步计划

运行第一个小程序，并观察 `intake -> audit -> delivery` 每个节点往 State 里写了什么。
