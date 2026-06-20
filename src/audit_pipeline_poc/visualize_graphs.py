"""Visualize LangGraph workflows as Mermaid diagrams.

大白话版本：

- 我们已经会跑图。
- 现在要能看图。
- Mermaid = 一种用文字描述流程图的格式。

本文件不会提交生成出来的图片或临时输出，只负责生成本地观察用的图文件。
"""

from __future__ import annotations

from pathlib import Path

from audit_pipeline_poc.basic_graph import build_graph as build_basic_graph
from audit_pipeline_poc.checkpointer_graph import build_graph as build_checkpointer_graph
from audit_pipeline_poc.conditional_graph import build_graph as build_conditional_graph
from audit_pipeline_poc.interrupt_graph import build_graph as build_interrupt_graph
from audit_pipeline_poc.reducer_graph import build_graph as build_reducer_graph
from audit_pipeline_poc.state_schema_graph import build_graph as build_state_schema_graph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "graphs"


def _save_mermaid(name: str, mermaid_text: str) -> Path:
    """保存 Mermaid 文本图。"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{name}.mmd"
    output_path.write_text(mermaid_text, encoding="utf-8")
    return output_path


def _save_png_if_supported(name: str, graph_object) -> Path | None:
    """如果当前 LangGraph/依赖支持，就额外保存 PNG。

    PNG 生成通常依赖额外环境或在线渲染能力。失败不影响学习主线，
    Mermaid 文本图才是最稳定的本地输出。
    """

    draw_mermaid_png = getattr(graph_object, "draw_mermaid_png", None)
    if draw_mermaid_png is None:
        return None

    try:
        png_bytes = draw_mermaid_png()
    except Exception as exc:  # pragma: no cover - 环境差异太大，不把它当测试失败
        print(f"[warn] PNG export skipped for {name}: {exc}")
        return None

    output_path = OUTPUT_DIR / f"{name}.png"
    output_path.write_bytes(png_bytes)
    return output_path


def export_graph(name: str, app) -> dict[str, str | None]:
    """导出一张图的 Mermaid 文本，能导 PNG 就顺手导 PNG。"""

    graph_object = app.get_graph()
    mermaid_text = graph_object.draw_mermaid()

    mermaid_path = _save_mermaid(name, mermaid_text)
    png_path = _save_png_if_supported(name, graph_object)

    return {
        "name": name,
        "mermaid": str(mermaid_path),
        "png": str(png_path) if png_path else None,
    }


def export_all_graphs() -> list[dict[str, str | None]]:
    """导出当前学习项目里已有的图。"""

    graphs = {
        "day1_basic_graph": build_basic_graph(),
        "day2_conditional_graph": build_conditional_graph(),
        "day4_state_schema_graph": build_state_schema_graph(),
        "day5_reducer_graph": build_reducer_graph(),
        "day6_checkpointer_graph": build_checkpointer_graph(),
        "day7_interrupt_graph": build_interrupt_graph(),
    }

    return [export_graph(name, app) for name, app in graphs.items()]


if __name__ == "__main__":
    results = export_all_graphs()

    print("Graph files generated:")
    for item in results:
        print(f"- {item['name']}")
        print(f"  Mermaid: {item['mermaid']}")
        if item["png"]:
            print(f"  PNG:     {item['png']}")
        else:
            print("  PNG:     skipped; Mermaid file is available")
