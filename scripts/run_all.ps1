$ErrorActionPreference = "Stop"

# 一键本地启动脚本：
# 1. 进入仓库根目录
# 2. 如果没有 .venv，就创建虚拟环境
# 3. 安装学习项目依赖
# 4. 运行 Day 1 直线流程
# 5. 运行 Day 2 分岔流程
# 6. 运行 Day 4 结构化 State 流程
# 7. 导出 Mermaid 流程图
# 8. 运行全部测试

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

Write-Host "== LangGraph study: local run ==" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "\n[1/7] .venv not found, creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "\n[1/7] .venv already exists." -ForegroundColor Green
}

Write-Host "\n[2/7] Installing dependencies..." -ForegroundColor Cyan
& $VenvPython -m pip install -e ".[dev]"

Write-Host "\n[3/7] Running Day 1 basic graph..." -ForegroundColor Cyan
& $VenvPython -m audit_pipeline_poc.basic_graph

Write-Host "\n[4/7] Running Day 2 conditional graph..." -ForegroundColor Cyan
& $VenvPython -m audit_pipeline_poc.conditional_graph

Write-Host "\n[5/7] Running Day 4 state schema graph..." -ForegroundColor Cyan
& $VenvPython -m audit_pipeline_poc.state_schema_graph

Write-Host "\n[6/7] Exporting graph diagrams..." -ForegroundColor Cyan
& $VenvPython -m audit_pipeline_poc.visualize_graphs

Write-Host "\n[7/7] Running tests..." -ForegroundColor Cyan
& $VenvPython -m pytest

Write-Host "\nAll checks passed. Humanity survives another command line session." -ForegroundColor Green
