"""
visualize.py  —  CONCEPT 12: See your graph as a picture
========================================================

Run it:     python visualize.py

LangGraph can draw any compiled graph. This script writes `graph.md`
containing a Mermaid diagram. Open it in VS Code's Markdown preview
(Ctrl+Shift+V), or paste the code into https://mermaid.live

  • Solid arrows  = normal edges
  • Dotted arrows = conditional edges / Command(goto=...)

This is a great way to check that your edges are wired the way you think!
"""

from pathlib import Path

from graph import graph
from news_subgraph import news_graph

main_diagram = graph.get_graph().draw_mermaid()
news_diagram = news_graph.get_graph().draw_mermaid()

output = Path(__file__).parent / "graph.md"
output.write_text(
    "# Main graph\n\n```mermaid\n" + main_diagram + "```\n\n"
    "# News subgraph (tool-calling agent)\n\n```mermaid\n" + news_diagram + "```\n",
    encoding="utf-8",
)
print(main_diagram)
print(f"Saved diagram to {output}")
