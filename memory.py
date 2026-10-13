"""
memory.py  —  CONCEPT 9: Memory with a Checkpointer
===================================================

🧠 The problem
--------------
By default a graph forgets everything once a run finishes. Run it again and
the state starts empty, so it can't answer "why did you say HOLD?".

✅ The solution: a CHECKPOINTER
------------------------------
A checkpointer SAVES the state after every step (a "checkpoint").
You enable it when compiling the graph:

    graph = builder.compile(checkpointer=MemorySaver())

Then you tell LangGraph WHICH conversation you're in with a `thread_id`:

    config = {"configurable": {"thread_id": "user-42"}}
    graph.invoke({"messages": [...]}, config)

  • Same thread_id  -> continues the same conversation (state is loaded back)
  • New thread_id   -> a fresh conversation with empty state

The checkpointer also makes these possible:
  • Human-in-the-loop: `interrupt()` needs somewhere to save the paused state.
  • Inspecting state:  graph.get_state(config).values
  • Time travel:       graph.get_state_history(config) lists every checkpoint.

Which checkpointer?
  • MemorySaver   -> stored in RAM. Simple, perfect for learning.
                     Everything is lost when the program exits.
  • SqliteSaver   -> stored in a .db file (pip install langgraph-checkpoint-sqlite)
  • PostgresSaver -> for production apps
They all work the same way, so switching later is a one-line change.
"""

from langgraph.checkpoint.memory import MemorySaver


def get_checkpointer() -> MemorySaver:
    """Return the checkpointer used by our graph."""
    return MemorySaver()
