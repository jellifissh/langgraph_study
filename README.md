# langgraph_study

这是一个用于学习 **LangGraph + Agent 工程思维** 的仓库。

当前目标：

- 不接 LLM。
- 不做多 Agent。
- 先跑通最小工作流：`START -> intake -> audit -> delivery -> END`。
- 再加入分岔路口：`audit -> passed / need_review / failed`。
- 用审计小案例理解 State（账本）、Node（点/工位）、Edge（线/路线）、Conditional Edge（分岔路口）、Graph（流程地图）。

## 一键启动

Windows 下推荐直接运行：

```bash
scripts\run_all.bat
```

或者在 PowerShell 中运行：

```powershell
.\scripts\run_all.ps1
```

这个脚本会自动执行：

1. 检查并创建 `.venv`。
2. 安装项目依赖。
3. 运行 Day 1 直线流程。
4. 运行 Day 2 分岔流程。
5. 运行全部测试。

## 手动安装

建议使用 Python 3.11+。

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

## 运行 Day 1：直线流程

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

## 运行 Day 2：分岔流程

```bash
python -m audit_pipeline_poc.conditional_graph
```

预期你会看到 3 个 case：

- `passed`：直接进入 `delivery`
- `need_review`：先进入 `review`，再进入 `delivery`
- `failed`：进入 `error_report`

## 运行测试

```bash
python -m pytest
```

## 当前你要理解的东西

- State = 账本：保存流程中后面还要用的关键数据。
- Node = 点 / 工位：一个处理步骤，比如 `intake`、`audit`、`delivery`。
- Edge = 线 / 路：从一个处理点走到下一个处理点。
- Conditional Edge = 分岔路口：根据账本里的状态决定下一步去哪。
- Graph = 流程地图：把点和线组织起来。
- compile = 装配机器：把流程图变成能运行的对象。
- invoke = 跑一次：把输入丢进去，得到最终状态。
