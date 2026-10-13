"""
state.py  —  CONCEPT 1: The State
=================================

🧠 What is "State" in LangGraph?
--------------------------------
A LangGraph app is a set of steps (called NODES) connected by arrows (EDGES).
The STATE is the shared "notebook" that is passed from node to node.

    ┌─────────┐   state   ┌─────────┐   state   ┌─────────┐
    │ node A  │ ────────▶ │ node B  │ ────────▶ │ node C  │
    └─────────┘           └─────────┘           └─────────┘

  • Every node RECEIVES the current state (a Python dict).
  • Every node RETURNS a dict with ONLY the keys it wants to change.
  • LangGraph MERGES that returned dict into the state for the next node.

We describe the shape of the state with a `TypedDict` — just a dict where
we list the keys and their types, so everyone knows what's inside.

🧩 What is a "Reducer"?
-----------------------
When a node returns {"some_key": new_value}, what should LangGraph do?

  1. DEFAULT (no reducer)  -> OVERWRITE the old value with the new value.
  2. WITH a reducer        -> COMBINE old + new using a function you choose.

You attach a reducer with `Annotated[type, reducer_function]`.

  • `add_messages` -> appends new chat messages to the existing list
                      (and updates a message if it has the same id).
  • `operator.add` -> for lists, `old + new`, i.e. append.

Reducers matter a lot for PARALLEL nodes: if three nodes run at the same time
and all write to the same key, LangGraph must know how to combine them.
(In our graph, the three analysts write to DIFFERENT keys, so no clash. But
they ALL append to `steps_log`, which works because it has a reducer.)
"""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """
    The shared state of our Stock Research Analyst graph.

    `total=False` means no key is required up front — nodes fill them in
    as the graph runs.
    """

    # ----------------------------------------------------------------------
    # 💬 Conversation history  (reducer: add_messages -> APPEND)
    # ----------------------------------------------------------------------
    # Holds the user's questions and the assistant's final answers.
    # Because of the checkpointer (see memory.py), this list is REMEMBERED
    # between runs, which is how follow-up questions work.
    messages: Annotated[list[AnyMessage], add_messages]

    # ----------------------------------------------------------------------
    # 🎯 What the user asked for  (filled by the `parse_request` node)
    # ----------------------------------------------------------------------
    intent: str  # "new_analysis" | "follow_up" | "unclear"
    ticker: str  # e.g. "AAPL", "RELIANCE.NS" (NSE), "500325.BO" (BSE)
    company_name: str  # e.g. "Apple Inc."
    market: str  # "US" or "India"

    # ----------------------------------------------------------------------
    # 📊 Analyst outputs  (no reducer -> each node OVERWRITES its own key)
    # ----------------------------------------------------------------------
    # These three are written by the three PARALLEL analyst nodes.
    fundamental_analysis: str
    technical_analysis: str
    news_analysis: str

    # ----------------------------------------------------------------------
    # 📝 Report + quality loop
    # ----------------------------------------------------------------------
    report: str  # the latest draft of the research report
    revision_count: int  # how many times the report has been (re)written
    critic_score: int  # quality score 1-10 given by the critic node
    critic_feedback: str  # what the critic wants improved
    human_feedback: str  # what YOU asked to change during human review

    # ----------------------------------------------------------------------
    # 🪵 Step log  (reducer: operator.add -> APPEND to the list)
    # ----------------------------------------------------------------------
    # Every node adds a short line here, e.g. ["parse_request: AAPL", ...].
    # Nodes return {"steps_log": ["my message"]} and LangGraph does
    # old_list + ["my message"] for us. Great for seeing the execution order!
    steps_log: Annotated[list[str], operator.add]
