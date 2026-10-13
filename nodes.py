"""
nodes.py  —  CONCEPT 6: Nodes
=============================

🧠 What is a Node?
------------------
A node is just a Python function:

    def my_node(state: AgentState) -> dict:
        ...do some work (call an LLM, call a tool, compute something)...
        return {"some_key": new_value}      # ONLY the keys you changed

Rules to remember:
  ✅ Read whatever you need from `state`.
  ✅ Return a dict of updates. LangGraph merges it into the state.
  ❌ Don't modify `state` in place (e.g. state["x"] = 1). Return updates instead.

Our nodes (in the order they usually run):

    parse_request          -> understand the user's message (structured output)
    ask_clarification      -> reply if we don't know which stock
    answer_follow_up       -> answer questions about an earlier report (memory)
    prepare_research       -> reset old values before a fresh analysis
    fundamental_analyst  ┐
    technical_analyst    ├─ run IN PARALLEL
    news_analyst         ┘  (lives in news_subgraph.py)
    report_writer          -> combine the 3 analyses into one report
    critic                 -> grade the report (may send it back = loop)
    human_review           -> YOU approve or request changes (human_review.py)
"""

from langchain_core.messages import AIMessage, SystemMessage

from config import get_llm
from prompts import (
    CLARIFY_MESSAGE,
    CRITIC_PROMPT,
    FOLLOW_UP_PROMPT,
    FUNDAMENTAL_ANALYST_PROMPT,
    PARSE_REQUEST_PROMPT,
    REPORT_WRITER_PROMPT,
    TECHNICAL_ANALYST_PROMPT,
)
from schemas import CritiqueResult, TickerRequest
from state import AgentState
from tools import get_fundamentals, get_price_history

# One shared LLM for all simple nodes.
llm = get_llm()


# ---------------------------------------------------------------------------
# 1. parse_request  —  uses STRUCTURED OUTPUT (see schemas.py)
# ---------------------------------------------------------------------------
def parse_request(state: AgentState) -> dict:
    """Figure out the intent and the ticker from the user's latest message."""
    parser = llm.with_structured_output(TickerRequest)

    # We pass the WHOLE conversation, so "what about its competitor?" works.
    result = parser.invoke([SystemMessage(content=PARSE_REQUEST_PROMPT)] + state["messages"])

    if result is None:  # the LLM failed to produce valid output
        result = TickerRequest(intent="unclear")

    ticker = result.ticker.upper().strip()
    return {
        "intent": result.intent,
        "ticker": ticker,
        "company_name": result.company_name,
        "market": result.market,
        "steps_log": [f"parse_request: intent={result.intent}, ticker={ticker or '-'}"],
    }


# ---------------------------------------------------------------------------
# 2. ask_clarification  —  a node that doesn't use an LLM at all
# ---------------------------------------------------------------------------
def ask_clarification(state: AgentState) -> dict:
    """Politely ask the user which stock they mean."""
    return {
        "messages": [AIMessage(content=CLARIFY_MESSAGE)],
        "steps_log": ["ask_clarification: asked user for a valid stock"],
    }


# ---------------------------------------------------------------------------
# 3. answer_follow_up  —  relies on MEMORY (the saved `messages` history)
# ---------------------------------------------------------------------------
def answer_follow_up(state: AgentState) -> dict:
    """Answer a question about an earlier report, using the chat history."""
    response = llm.invoke([SystemMessage(content=FOLLOW_UP_PROMPT)] + state["messages"])
    return {
        "messages": [response],
        "steps_log": ["answer_follow_up: answered from conversation memory"],
    }


# ---------------------------------------------------------------------------
# 4. prepare_research  —  reset per-analysis values
# ---------------------------------------------------------------------------
def prepare_research(state: AgentState) -> dict:
    """
    Because the checkpointer REMEMBERS the state between runs, values from
    the PREVIOUS stock (old report, old revision count...) are still there!
    Before starting a new analysis we reset them.

    This node is also the "fan-out" point: three edges leave it, so the
    three analysts start at the same time (see graph.py).
    """
    return {
        "report": "",
        "revision_count": 0,
        "critic_score": 0,
        "critic_feedback": "",
        "human_feedback": "",
        "steps_log": [f"prepare_research: starting research on {state['ticker']} ({state['market']})"],
    }


# ---------------------------------------------------------------------------
# 5. fundamental_analyst  —  calls a TOOL directly, then the LLM
# ---------------------------------------------------------------------------
def fundamental_analyst(state: AgentState) -> dict:
    """Fetch fundamentals with a tool and let the LLM interpret them."""
    # Calling a tool ourselves: tool.invoke({...arguments...})
    data = get_fundamentals.invoke({"ticker": state["ticker"]})

    prompt = FUNDAMENTAL_ANALYST_PROMPT.format(company=state["company_name"], ticker=state["ticker"], data=data)
    response = llm.invoke(prompt)

    # This node writes ONLY its own key, so it never clashes with the
    # other two analysts running in parallel.
    return {
        "fundamental_analysis": response.text,
        "steps_log": ["fundamental_analyst: done"],
    }


# ---------------------------------------------------------------------------
# 6. technical_analyst  —  same pattern, different tool
# ---------------------------------------------------------------------------
def technical_analyst(state: AgentState) -> dict:
    """Fetch price indicators with a tool and let the LLM interpret them."""
    data = get_price_history.invoke({"ticker": state["ticker"]})

    prompt = TECHNICAL_ANALYST_PROMPT.format(company=state["company_name"], ticker=state["ticker"], data=data)
    response = llm.invoke(prompt)

    return {
        "technical_analysis": response.text,
        "steps_log": ["technical_analyst: done"],
    }


# (news_analyst lives in news_subgraph.py because it is a subgraph)


# ---------------------------------------------------------------------------
# 7. report_writer  —  the "fan-in" node (waits for all 3 analysts)
# ---------------------------------------------------------------------------
def report_writer(state: AgentState) -> dict:
    """Combine the three analyses into one report. Also used for rewrites."""
    # If this is a REWRITE, tell the LLM what to fix.
    extra = ""
    if state.get("critic_feedback"):
        extra += f"\nThe editor's feedback on your previous draft (fix this!): {state['critic_feedback']}"
    if state.get("human_feedback"):
        extra += f"\nThe client's requested changes (top priority!): {state['human_feedback']}"

    prompt = REPORT_WRITER_PROMPT.format(
        company=state["company_name"],
        ticker=state["ticker"],
        fundamental=state.get("fundamental_analysis", "N/A"),
        technical=state.get("technical_analysis", "N/A"),
        news=state.get("news_analysis", "N/A"),
        extra_instructions=extra,
    )
    response = llm.invoke(prompt)

    revision = state.get("revision_count", 0) + 1
    return {
        "report": response.text,
        "revision_count": revision,
        "steps_log": [f"report_writer: wrote draft #{revision}"],
    }


# ---------------------------------------------------------------------------
# 8. critic  —  structured output used to drive a LOOP
# ---------------------------------------------------------------------------
def critic(state: AgentState) -> dict:
    """Grade the report. The routing function in edges.py reads the score."""
    grader = llm.with_structured_output(CritiqueResult)
    result = grader.invoke(CRITIC_PROMPT.format(report=state["report"]))

    if result is None:  # if grading fails, don't block the user
        result = CritiqueResult(score=10, feedback="None")

    return {
        "critic_score": result.score,
        "critic_feedback": result.feedback,
        "steps_log": [f"critic: score={result.score}/10"],
    }
