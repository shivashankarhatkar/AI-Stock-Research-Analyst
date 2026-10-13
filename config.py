"""
config.py  —  STEP 0: Setup (LLM + LangSmith tracing)
=====================================================

This file does two things:
  1. Loads your API keys from the `.env` file.
  2. Creates the LLM (Google Gemini) that every node in our graph will use.

📌 LangSmith tracing — how does it work?
----------------------------------------
LangSmith does NOT need any special code inside your graph!
LangChain / LangGraph automatically check for these environment variables:

    LANGSMITH_TRACING=true          -> turns tracing ON
    LANGSMITH_API_KEY=lsv2_...      -> your LangSmith key
    LANGSMITH_PROJECT=stock-analyst -> the project name shown in the dashboard

If they are set, EVERY graph run, node, LLM call and tool call is sent to
https://smith.langchain.com where you can see a visual tree of what happened,
how long each step took, the exact prompts and the exact LLM responses.

So all we have to do here is load the .env file. That's it.
"""

import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Read the `.env` file and put its values into environment variables.
# (This must run BEFORE any LangChain object is created, so tracing is picked up.)
load_dotenv()


# ---------------------------------------------------------------------------
# Simple settings (change these to experiment)
# ---------------------------------------------------------------------------

# Which Gemini model to use. "gemini-2.5-flash" is fast and has a free tier.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# How many times the "critic" may send the report back for rewriting
# before we stop looping. (Prevents an infinite loop in our graph!)
MAX_REVISIONS = 2

# The minimum quality score (out of 10) the critic needs to accept a report.
MIN_QUALITY_SCORE = 7


def get_llm(temperature: float = 0.2) -> ChatGoogleGenerativeAI:
    """
    Create and return a Gemini chat model.

    `ChatGoogleGenerativeAI` is LangChain's wrapper around Gemini.
    Because it is a LangChain "chat model", it gives us useful extras for free:
      - .invoke(messages)               -> normal chat call
      - .bind_tools([...])              -> lets the LLM call our Python tools
      - .with_structured_output(Model)  -> forces the LLM to return typed data
    and every call is automatically traced in LangSmith.

    It reads your key from the GOOGLE_API_KEY environment variable.
    """
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=temperature,  # low = more focused / less random answers
        max_retries=3,  # retry automatically if Gemini rate-limits us
    )


def check_setup() -> None:
    """Print a friendly warning if a key is missing (called from main.py)."""
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  GOOGLE_API_KEY is missing. Add it to your .env file.")

    if os.getenv("LANGSMITH_TRACING", "").lower() == "true" and os.getenv("LANGSMITH_API_KEY"):
        project = os.getenv("LANGSMITH_PROJECT", "default")
        print(f"🔍 LangSmith tracing is ON  ->  project: '{project}'")
    else:
        print("ℹ️  LangSmith tracing is OFF (set LANGSMITH_TRACING=true and LANGSMITH_API_KEY in .env)")
