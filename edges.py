"""
edges.py  —  CONCEPT 8: Conditional Edges (Routing)
===================================================

🧠 Two kinds of edges
---------------------
1. NORMAL edge — always goes to the same next node:
       builder.add_edge("report_writer", "critic")

2. CONDITIONAL edge — a ROUTING FUNCTION looks at the state and returns
   the NAME of the next node:
       builder.add_conditional_edges("critic", route_after_critic)

A routing function:
  • receives the state (just like a node)
  • returns a string: the name of the next node (or END)
  • must NOT change the state (it only decides the direction)

Using `Literal[...]` as the return type lists every possible destination.
LangGraph uses it to draw the arrows in the graph picture (visualize.py).

(There's a third way to route: return a `Command(goto=...)` from inside a
node. See human_review.py.)
"""

from typing import Literal

from config import MAX_REVISIONS, MIN_QUALITY_SCORE
from state import AgentState


def route_after_parse(state: AgentState) -> Literal["prepare_research", "answer_follow_up", "ask_clarification"]:
    """
    After understanding the request, decide which path to take:

        new_analysis  ->  prepare_research   (the full research pipeline)
        follow_up     ->  answer_follow_up   (answer from memory)
        unclear       ->  ask_clarification  (ask the user again)
    """
    if state["intent"] == "new_analysis" and state.get("ticker"):
        return "prepare_research"
    if state["intent"] == "follow_up":
        return "answer_follow_up"
    return "ask_clarification"


def route_after_critic(state: AgentState) -> Literal["report_writer", "human_review"]:
    """
    This creates a LOOP:  report_writer -> critic -> report_writer -> ...

    Every loop needs a way OUT, otherwise it could run forever. We stop when:
      • the report is good enough, OR
      • we've already rewritten it MAX_REVISIONS times.

    (LangGraph also has a safety net called `recursion_limit` (default 25 steps)
    that raises an error if a graph runs too many steps.)
    """
    good_enough = state.get("critic_score", 0) >= MIN_QUALITY_SCORE
    out_of_attempts = state.get("revision_count", 0) > MAX_REVISIONS

    if good_enough or out_of_attempts:
        return "human_review"
    return "report_writer"
