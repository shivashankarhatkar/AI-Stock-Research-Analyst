"""
schemas.py  —  CONCEPT 2: Structured Output
===========================================

🧠 The problem
--------------
LLMs normally reply with free text, e.g.
    "Sure! The ticker for Reliance is RELIANCE.NS on the NSE..."
Our Python code can't easily make decisions from a sentence like that.

✅ The solution: structured output
----------------------------------
We describe the EXACT shape we want using a Pydantic model (a typed class),
then call:

    llm.with_structured_output(TickerRequest).invoke(messages)

and we get back a real Python object:

    TickerRequest(intent="new_analysis", ticker="RELIANCE.NS", ...)

The `Field(description=...)` text is sent to the LLM, so it knows what each
field means. Write these descriptions like instructions!

Why does this matter for LangGraph?
Because our ROUTING decisions (which node runs next) are based on these
fields, e.g. `if state["intent"] == "new_analysis": go to research`.
"""

from typing import Literal

from pydantic import BaseModel, Field


class TickerRequest(BaseModel):
    """Used by the `parse_request` node to understand the user's message."""

    intent: Literal["new_analysis", "follow_up", "unclear"] = Field(
        description=(
            "'new_analysis' if the user wants a stock researched/analysed; "
            "'follow_up' if they ask a question about a report already given earlier in the chat; "
            "'unclear' if no company or stock can be identified."
        )
    )
    ticker: str = Field(
        default="",
        description=(
            "The Yahoo Finance ticker symbol. US stocks: plain symbol (e.g. AAPL, MSFT). "
            "Indian NSE stocks: add '.NS' (e.g. RELIANCE.NS, TCS.NS). "
            "Indian BSE stocks: add '.BO' only if the user mentions BSE. "
            "Empty string if unclear."
        ),
    )
    company_name: str = Field(default="", description="Full company name, e.g. 'Apple Inc.'")
    market: Literal["US", "India", ""] = Field(default="", description="Which market the stock trades in.")


class CritiqueResult(BaseModel):
    """Used by the `critic` node to grade the report."""

    score: int = Field(description="Quality score from 1 (poor) to 10 (excellent).")
    feedback: str = Field(
        description="Specific, actionable suggestions to improve the report. Say 'None' if it is excellent."
    )
