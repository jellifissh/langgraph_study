# langgraph_study

这是一个用于学习 **LangGraph + Agent 工程思维** 的仓库。

当前第 1 天目标：

- 不接 LLM。
- 不做多 Agent。
- 只跑通最小工作流：`START -> intake -> audit -> delivery -> END`。
- 用最小审计案例理解 State（账本）、Node（点/工位）、Edge（线/路线）、Graph（流程地图）。

## 安装

建议使用 Python 3.11+。

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

## 运行第一个小程序

```bash
python -m audit_pipeline_poc.basic_graph
```

预期你会看到一个 JSON 输出，里面包含：

- `company`
- `revenue`
- `net_profit`
- `profit_margin`
- `audit_status`
- `delivery_message`

## 运行测试

```bash
pytest
```

## 第 1 天你要理解的东西

- State = 账本：保存流程中后面还要用的关键数据。
- Node = 点 / 工位：一个处理步骤，比如 `intake`、`audit`、`delivery`。
- Edge = 线 / 路：从一个处理点走到下一个处理点。
- Graph = 流程地图：把点和线组织起来。
- compile = 装配机器：把流程图变成能运行的对象。
- invoke = 跑一次：把输入丢进去，得到最终状态。
