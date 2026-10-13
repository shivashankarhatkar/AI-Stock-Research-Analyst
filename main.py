"""
main.py  —  CONCEPT 11: Running the graph (streaming, threads, resuming)
========================================================================

Run it:     python main.py

Things to try:
    > Analyse Apple
    > Research TCS
    > Analyse Reliance on BSE
    > Why did you give that verdict?      (follow-up -> uses memory)
    > What about its competitor Infosys?  (follow-up that triggers a NEW analysis)
    > state                               (peek at the saved state)
    > new                                 (start a new conversation thread)
    > quit

🧠 Concepts used here
---------------------
• invoke vs stream
    graph.invoke(input, config)  -> runs everything, returns the final state.
    graph.stream(input, config)  -> yields an update after EACH node finishes,
                                    so we can show progress live.
  stream_mode options:
    "updates"  -> {node_name: what_that_node_returned}   (used here)
    "values"   -> the FULL state after every step
    "messages" -> LLM tokens one by one (for chat-style typing effects)

• config
    {"configurable": {"thread_id": ...}}  -> which conversation (memory.py)
    "run_name", "tags", "metadata"        -> labels shown in LangSmith, so you
                                             can find and filter your runs easily.

• Resuming after interrupt()
    When human_review pauses, the stream yields {"__interrupt__": (...)}.
    We ask the user, then call graph.stream(Command(resume=answer), config).
"""

import sys
import uuid
from datetime import date
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from config import check_setup  # importing config also loads .env (and LangSmith settings)
from graph import graph

# Make emojis print correctly in the Windows terminal.
sys.stdout.reconfigure(encoding="utf-8")

REPORTS_DIR = Path(__file__).parent / "reports"


def make_config(thread_id: str) -> dict:
    """The config passed with EVERY call for this conversation."""
    return {
        "configurable": {"thread_id": thread_id},  # 🧠 memory: which conversation
        "run_name": "stock-research-analyst",  # 🔍 LangSmith: name of the trace
        "tags": ["learning", "stock-analyst"],  # 🔍 LangSmith: filterable tags
        "metadata": {"thread_id": thread_id},  # 🔍 LangSmith: extra info
    }


def stream_graph(graph_input, config: dict):
    """
    Run the graph with streaming and print each node as it finishes.
    Returns the interrupt payload if the graph paused, otherwise None.
    """
    for chunk in graph.stream(graph_input, config, stream_mode="updates"):
        # Each chunk looks like {"node_name": {...the dict that node returned...}}
        for node_name, update in chunk.items():
            if node_name == "__interrupt__":
                # The graph paused! `update` is a tuple of Interrupt objects.
                return update[0].value

            # Print the step's log line (every node adds one to steps_log).
            for line in (update or {}).get("steps_log", []):
                print(f"   ⚙️  {line}")
    return None


def save_report(state: dict) -> Path:
    """Save an approved report as a markdown file in the reports/ folder."""
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{state['ticker'].replace('.', '_')}_{date.today()}.md"
    path.write_text(state["report"], encoding="utf-8")
    return path


def handle_message(user_text: str, config: dict) -> None:
    """Send one user message through the graph, including any human reviews."""
    # The input only contains what we want to ADD to the state.
    # Thanks to the add_messages reducer, this message is APPENDED to history.
    graph_input = {"messages": [HumanMessage(content=user_text)]}
    was_reviewed = False

    while True:
        pause = stream_graph(graph_input, config)
        if pause is None:
            break  # the graph reached END

        # ----- ⏸️ Human-in-the-loop: show the report and ask for a decision -----
        was_reviewed = True
        print("\n" + "=" * 70)
        print(pause["report"])
        print("=" * 70)
        print(f"🧐 Critic score: {pause['critic_score']}/10")
        answer = input(f"👤 {pause['question']}\n> ")

        # ▶️ Resume the paused graph. Command(resume=...) becomes the return
        # value of interrupt() inside human_review.py.
        graph_input = Command(resume=answer)

    # ----- Show the result -----
    # get_state() reads the latest checkpoint saved by the checkpointer.
    final_state = graph.get_state(config).values
    if was_reviewed:
        path = save_report(final_state)
        print(f"\n✅ Report approved and saved to: {path}")
    else:
        print(f"\n🤖 {final_state['messages'][-1].text}")


def show_state(config: dict) -> None:
    """Peek inside the checkpointer: the saved state for this thread."""
    snapshot = graph.get_state(config)
    values = snapshot.values
    print(f"\n📦 Saved state for thread '{config['configurable']['thread_id']}':")
    print(f"   messages in memory : {len(values.get('messages', []))}")
    print(f"   last ticker        : {values.get('ticker', '-')}")
    print(f"   revisions          : {values.get('revision_count', '-')}")
    print(f"   critic score       : {values.get('critic_score', '-')}")
    print(f"   checkpoints saved  : {len(list(graph.get_state_history(config)))}")
    print("   step log:")
    for line in values.get("steps_log", []):
        print(f"     - {line}")


def main() -> None:
    check_setup()
    thread_id = str(uuid.uuid4())[:8]
    config = make_config(thread_id)

    print("\n📈 Personal Stock Research Analyst  (US + Indian stocks)")
    print(f"   Conversation thread: {thread_id}")
    print("   Try: 'Analyse Apple', 'Research TCS', then ask a follow-up.")
    print("   Commands: state | new | quit\n")

    while True:
        user_text = input("💬 You: ").strip()
        if not user_text:
            continue
        if user_text.lower() in ("quit", "exit", "q"):
            break
        if user_text.lower() == "state":
            show_state(config)
            continue
        if user_text.lower() == "new":
            thread_id = str(uuid.uuid4())[:8]
            config = make_config(thread_id)
            print(f"🆕 New conversation thread: {thread_id} (memory is empty again)")
            continue

        handle_message(user_text, config)
        print()


if __name__ == "__main__":
    main()
