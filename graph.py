"""
graph.py  —  CONCEPT 10: Building the Graph (putting it all together)
=====================================================================

This is the heart of the project. All the pieces from the other files are
wired together here. Building any LangGraph app follows the same 5 steps:

    1. builder = StateGraph(State)          # say what the state looks like
    2. builder.add_node("name", function)   # add the steps
    3. builder.add_edge(...)                # connect them
       builder.add_conditional_edges(...)   # ...including the branches
    4. graph = builder.compile(...)         # turn the blueprint into a runnable app
    5. graph.invoke(...) / graph.stream(...)  # run it (see main.py)

Our graph:

                         START
                           │
                     parse_request
            ┌──────────────┼────────────────┐   (conditional edge)
            ▼              ▼                ▼
   ask_clarification  answer_follow_up  prepare_research
            │              │                │
           END            END     ┌─────────┼─────────┐   (fan-out = PARALLEL)
                                  ▼         ▼         ▼
                         fundamental   technical    news (subgraph)
                                  └─────────┼─────────┘   (fan-in = wait for all 3)
                                            ▼
                                     report_writer  ◀────────┐
                                            │                │
                                          critic ── low score┘   (LOOP)
                                            │ good score
                                            ▼
                                      human_review ── "change X" ─▶ report_writer
                                            │ "approve"
                                            ▼
                                           END
"""

from langgraph.graph import END, START, StateGraph

from edges import route_after_critic, route_after_parse
from human_review import human_review
from memory import get_checkpointer
from news_subgraph import news_analyst_node
from nodes import (
    answer_follow_up,
    ask_clarification,
    critic,
    fundamental_analyst,
    parse_request,
    prepare_research,
    report_writer,
    technical_analyst,
)
from state import AgentState


def build_graph():
    # ------------------------------------------------------------------
    # STEP 1: Create the builder and tell it the shape of our state.
    # ------------------------------------------------------------------
    builder = StateGraph(AgentState)

    # ------------------------------------------------------------------
    # STEP 2: Add the nodes.  add_node("unique name", python_function)
    # ------------------------------------------------------------------
    builder.add_node("parse_request", parse_request)
    builder.add_node("ask_clarification", ask_clarification)
    builder.add_node("answer_follow_up", answer_follow_up)
    builder.add_node("prepare_research", prepare_research)
    builder.add_node("fundamental_analyst", fundamental_analyst)
    builder.add_node("technical_analyst", technical_analyst)
    builder.add_node("news_analyst", news_analyst_node)  # runs a subgraph inside
    builder.add_node("report_writer", report_writer)
    builder.add_node("critic", critic)
    builder.add_node("human_review", human_review)  # routes itself using Command

    # ------------------------------------------------------------------
    # STEP 3: Add the edges.
    # ------------------------------------------------------------------

    # START is a special name meaning "where the graph begins".
    builder.add_edge(START, "parse_request")

    # CONDITIONAL edge: route_after_parse() returns the next node's name.
    builder.add_conditional_edges("parse_request", route_after_parse)

    # These two paths are finished after one step. END = "stop here".
    builder.add_edge("ask_clarification", END)
    builder.add_edge("answer_follow_up", END)

    # FAN-OUT: three normal edges leave the same node.
    # LangGraph runs all three targets AT THE SAME TIME (in one "super-step").
    builder.add_edge("prepare_research", "fundamental_analyst")
    builder.add_edge("prepare_research", "technical_analyst")
    builder.add_edge("prepare_research", "news_analyst")

    # FAN-IN: passing a LIST of start nodes means
    # "run report_writer only after ALL of these have finished".
    builder.add_edge(["fundamental_analyst", "technical_analyst", "news_analyst"], "report_writer")

    builder.add_edge("report_writer", "critic")

    # LOOP: the critic either sends the report back or forward.
    builder.add_conditional_edges("critic", route_after_critic)

    # No edges are needed out of human_review: it returns
    # Command(goto="report_writer" or END) itself.

    # ------------------------------------------------------------------
    # STEP 4: Compile. The checkpointer gives us memory + interrupts.
    # ------------------------------------------------------------------
    return builder.compile(checkpointer=get_checkpointer())


# Build once when this module is imported, so main.py can just import it.
graph = build_graph()
