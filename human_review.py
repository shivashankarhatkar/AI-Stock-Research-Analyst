"""
human_review.py  —  CONCEPT 7: Human-in-the-Loop  (interrupt + Command)
=======================================================================

🧠 Why?
-------
In real apps you often want a person to check the AI's work before it's
final (approve a trade, send an email, publish a report...).

🛑 `interrupt(value)`
---------------------
Calling `interrupt(...)` inside a node PAUSES the whole graph:
  1. The graph saves its state (this REQUIRES a checkpointer, see memory.py).
  2. `value` is handed back to your app, under the "__interrupt__" key.
  3. Your app shows it to the user and collects their answer.
  4. Your app RESUMES the graph with:  graph.invoke(Command(resume=answer), config)
  5. The node runs again FROM THE TOP, and this time `interrupt(...)`
     RETURNS `answer` instead of pausing.

  ⚠️ Because the node restarts from the top on resume, don't put
     side effects (like saving files) BEFORE the interrupt() call.

🧭 `Command(goto=..., update=...)`
----------------------------------
A node can return a `Command` instead of a dict. It does two things at once:
  • update=  -> change the state (same as returning a dict)
  • goto=    -> choose the NEXT node directly (routing from inside a node!)

The return type `Command[Literal["report_writer", "__end__"]]` tells
LangGraph which nodes this node may jump to, so it can draw the graph.
"""

from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.graph import END
from langgraph.types import Command, interrupt

from state import AgentState


def human_review(state: AgentState) -> Command[Literal["report_writer", "__end__"]]:
    """Pause, show the report to the human, then finish or rewrite."""

    # ⏸️ The graph STOPS here until main.py resumes it with Command(resume=...)
    answer = interrupt(
        {
            "report": state["report"],
            "critic_score": state.get("critic_score"),
            "question": "Type 'approve' to accept, or describe what you want changed:",
        }
    )

    # ▶️ We get here only AFTER the human has answered.
    if str(answer).strip().lower() in ("approve", "approved", "yes", "y", "ok", ""):
        # Save the final report into the chat history so follow-up
        # questions ("why HOLD?") can refer to it later.
        return Command(
            goto=END,
            update={
                "messages": [AIMessage(content=state["report"])],
                "steps_log": ["human_review: APPROVED ✅"],
            },
        )

    # The human wants changes -> go back to the writer with their feedback.
    return Command(
        goto="report_writer",
        update={
            "human_feedback": str(answer),
            "critic_feedback": "",  # the human's opinion replaces the critic's
            "steps_log": [f"human_review: changes requested -> '{answer}'"],
        },
    )
