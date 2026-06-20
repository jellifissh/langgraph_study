# Agent 工程学习地图

## 1. 我们到底要解决什么问题

我们不是为了背 LangGraph 名词，而是为了学会把一个 Agent 系统拆成可控流程。

财务审计 Agent 的最小问题是：

```text
输入财务字段 -> 检查字段 -> 计算指标 -> 得出审计结果 -> 输出报告
```

如果以后流程变复杂，还会出现：

- 数据缺失怎么办？
- 审计异常要不要人工复核？
- 中途失败怎么恢复？
- 哪一步写错了怎么定位？
- 哪些结果能自动通过，哪些必须留给人？

这就是 Agent 工程问题。

## 2. 普通函数链为什么会失控

普通 Python 可以直接写：

```text
intake() -> audit() -> delivery()
```

流程很短时没问题。

但一旦出现分支、暂停、恢复、人工复核、测试追踪，流程就会藏在一堆 `if/else` 里面。

LangGraph 的价值不是让代码更神秘，而是让流程更清楚。

## 3. LangGraph 在 Agent 工程里的位置

大白话：

- State = 账本
- Node = 点 / 工位
- Edge = 线 / 路
- Graph = 流程地图
- Conditional Edge = 分岔路口
- Checkpointer = 存档点
- Interrupt = 暂停等人确认

第 1 天只学前 4 个：账本、点、线、流程地图。

## 4. 审计流水线的图结构

第 1 天的最小流程：

```text
START
  ↓
intake
  ↓
audit
  ↓
delivery
  ↓
END
```

现在还没有分支。先把直线流程跑通。

## 5. 必须先掌握的 20%

- State 为什么是共享账本
- Node 为什么应该职责单一
- Edge 为什么要显式表达下一步
- Graph 为什么比藏在函数调用里的流程更清楚
- invoke 为什么代表“跑一次完整流程”

## 6. 暂时只需要认识的 60%

- Conditional Edge
- Checkpointer
- Interrupt
- Reducer
- Stream
- ToolNode
- Subgraph
- Multi-agent

这些后面逐个学，现在先别碰。第一天就全学，属于把脑子当 Docker 容器硬塞镜像，最后只能风扇起飞。

## 7. MVP 后再深入的 20%

- 真实人工复核
- 持久化恢复
- 工具调用边界
- 测试与可观察性
- 如何迁移到真实 `datefac_agent`

## 8. 本项目最终验收标准

最终要能做出一个简化版财务审计 Agent 流水线：

```text
intake -> normalize -> audit -> route -> review/delivery
```

并且能说清楚：

- 每个节点为什么这样拆
- 哪些字段进入 State
- 哪些分支应该显式化
- 哪些步骤需要人工复核
- 哪些设计只是学习 demo，不能直接上生产
