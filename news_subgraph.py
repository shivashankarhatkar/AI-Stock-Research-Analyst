"""
news_subgraph.py  —  CONCEPT 4: A Tool-Calling Agent  +  CONCEPT 5: Subgraphs
=============================================================================

This file builds a SMALL graph of its own: a "news agent" that decides by
itself which tools to call. The main graph then uses it as ONE step.

🧠 Part A — The tool-calling loop (the "ReAct" agent pattern)
------------------------------------------------------------

        START
          │
          ▼
    ┌────────────┐   LLM asked for a tool?   ┌────────────┐
    │ news_agent │ ───────── YES ──────────▶ │   tools    │
    │   (LLM)    │ ◀──────────────────────── │ (ToolNode) │
    └────────────┘     tool results          └────────────┘
          │
          NO (LLM wrote a final answer)
          ▼
         END

  1. `news_agent` calls the LLM. The LLM either:
       a) asks to call a tool  (message has `.tool_calls`), or
       b) writes its final answer.
  2. `tools_condition` (a ready-made routing function from LangGraph) checks
     which one happened and routes to "tools" or END.
  3. `ToolNode` (a ready-made node from LangGraph) runs the requested tools
     and adds their results to `messages` as ToolMessages.
  4. We loop back to `news_agent`, which now SEES the tool results.

This is a CYCLE in the graph — something LangGraph is especially good at.

🧠 Part B — Subgraphs
---------------------
A compiled graph can be used inside another graph. Benefits:
  • Each piece can be built and tested on its own.
  • The subgraph can have its OWN private state (here: NewsState), so all the
    tool-call messages stay inside it and do not clutter the main graph's
    `messages` list.

Because NewsState is different from the main AgentState, we call the subgraph
from inside a normal node function (`news_analyst_node`) and translate the
state in and out. (If both graphs used the same state keys, you could
instead add the compiled subgraph directly: builder.add_node("news", news_graph).)
"""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from config import get_llm
from prompts import NEWS_ANALYST_PROMPT
from state import AgentState
from tools import NEWS_AGENT_TOOLS


# ---------------------------------------------------------------------------
# 1. The subgraph's own, private state
# ---------------------------------------------------------------------------
class NewsState(TypedDict):
    # The conversation between the news agent and its tools.
    # `add_messages` appends each new LLM message / tool result.
    messages: Annotated[list[AnyMessage], add_messages]


# ---------------------------------------------------------------------------
# 2. The LLM node
# ---------------------------------------------------------------------------
# `.bind_tools(...)` tells Gemini which tools exist (name + docstring + args).
# Gemini can now reply with a tool call instead of text.
news_llm = get_llm().bind_tools(NEWS_AGENT_TOOLS)


def news_agent(state: NewsState) -> dict:
    """Call the LLM with the conversation so far (including any tool results)."""
    response = news_llm.invoke(state["messages"])
    # Return only what changed. add_messages will APPEND this to the list.
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# 3. Build the subgraph
# ---------------------------------------------------------------------------
def build_news_subgraph():
    builder = StateGraph(NewsState)

    builder.add_node("news_agent", news_agent)
    # ToolNode = prebuilt node that executes whatever tool calls the LLM made.
    builder.add_node("tools", ToolNode(NEWS_AGENT_TOOLS))

    builder.add_edge(START, "news_agent")

    # tools_condition returns "tools" if the last message has tool calls,
    # otherwise END. That's our conditional edge.
    builder.add_conditional_edges("news_agent", tools_condition)

    # After running tools, always go back to the LLM so it can read the results.
    builder.add_edge("tools", "news_agent")

    return builder.compile()


news_graph = build_news_subgraph()


# ---------------------------------------------------------------------------
# 4. The wrapper node used by the MAIN graph
# ---------------------------------------------------------------------------
def news_analyst_node(state: AgentState) -> dict:
    """
    Main-graph node that runs the news subgraph.

    Translate state IN  : AgentState (ticker, company)  ->  NewsState (messages)
    Translate state OUT : NewsState (last message)      ->  AgentState (news_analysis)
    """
    prompt = NEWS_ANALYST_PROMPT.format(company=state["company_name"], ticker=state["ticker"])
    sub_input = {
        "messages": [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Research the latest news for {state['company_name']} ({state['ticker']})."),
        ]
    }

    # Run the whole subgraph (it may loop through tools several times).
    sub_result = news_graph.invoke(sub_input)

    # The LAST message is the agent's final written summary.
    final_answer = sub_result["messages"][-1].text
    return {
        "news_analysis": final_answer,
        "steps_log": ["news_analyst: news researched by the tool-calling subgraph"],
    }
