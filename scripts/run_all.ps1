$ErrorActionPreference = "Stop"

# 一键本地启动脚本：
# 1. 进入仓库根目录
# 2. 如果没有 .venv，就创建虚拟环境
# 3. 安装学习项目依赖
# 4. 逐日运行学习 demo
# 5. 导出 Mermaid 流程图
# 6. 运行全部测试
#
# 注意：PowerShell 的 $ErrorActionPreference 对 python/pytest 这种原生命令不总是可靠。
# 所以这里显式检查 $LASTEXITCODE。失败就立刻退出，别再假装 All checks passed。
# 软件系统已经够会装没事了，脚本别跟着学。

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

Write-Host "== LangGraph study: local run ==" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Invoke-Step {
    param(
        [string]$Title,
        [string[]]$Arguments
    )

    Write-Host "\n$Title" -ForegroundColor Cyan
    & $VenvPython @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Host "\n[failed] $Title exited with code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "\n[1/16] .venv not found, creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "\n[failed] Failed to create .venv" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} else {
    Write-Host "\n[1/16] .venv already exists." -ForegroundColor Green
}

Invoke-Step "[2/16] Installing dependencies..." @("-m", "pip", "install", "-e", ".[dev]")
Invoke-Step "[3/16] Running Day 1 basic graph..." @("-m", "audit_pipeline_poc.basic_graph")
Invoke-Step "[4/16] Running Day 2 conditional graph..." @("-m", "audit_pipeline_poc.conditional_graph")
Invoke-Step "[5/16] Running Day 4 state schema graph..." @("-m", "audit_pipeline_poc.state_schema_graph")
Invoke-Step "[6/16] Running Day 5 reducer graph..." @("-m", "audit_pipeline_poc.reducer_graph")
Invoke-Step "[7/16] Running Day 6 checkpointer graph..." @("-m", "audit_pipeline_poc.checkpointer_graph")
Invoke-Step "[8/16] Running Day 7 interrupt graph..." @("-m", "audit_pipeline_poc.interrupt_graph")
Invoke-Step "[9/16] Running Day 8 interrupt safety graph..." @("-m", "audit_pipeline_poc.interrupt_safety_graph")
Invoke-Step "[10/16] Running Day 9 idempotency graph..." @("-m", "audit_pipeline_poc.idempotency_graph")
Invoke-Step "[11/16] Running Day 10 outbox graph..." @("-m", "audit_pipeline_poc.outbox_graph")
Invoke-Step "[12/16] Running Day 11 tool calling graph..." @("-m", "audit_pipeline_poc.tool_calling_graph")
Invoke-Step "[13/16] Running Day 12 LLM planner graph..." @("-m", "audit_pipeline_poc.llm_planner_graph")
Invoke-Step "[14/16] Running Day 13 agent loop graph..." @("-m", "audit_pipeline_poc.agent_loop_graph")
Invoke-Step "[15/16] Exporting graph diagrams..." @("-m", "audit_pipeline_poc.visualize_graphs")
Invoke-Step "[16/16] Running tests..." @("-m", "pytest")

Write-Host "\nAll checks passed. Humanity survives another command line session." -ForegroundColor Green
