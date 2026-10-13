# 8. Memory (Checkpointer)

Without memory, every run starts with an empty state. A **checkpointer** saves the state after every step, and a **`thread_id`** says which conversation to load.

```python
graph  = builder.compile(checkpointer=MemorySaver())      # memory.py / graph.py
config = {"configurable": {"thread_id": "a1b2c3"}}         # main.py
graph.invoke({"messages": [HumanMessage("Analyse Apple")]}, config)
```

## Threads = separate conversations

```mermaid
flowchart LR
    subgraph T1["thread_id = 'a1b2'"]
        direction TB
        m1["Analyse Apple"] --> m2["report..."] --> m3["Why HOLD?"] --> m4["Because... ✅ remembers"]
    end
    subgraph T2["thread_id = 'z9y8'"]
        direction TB
        n1["Why HOLD?"] --> n2["Which stock? ❓ empty memory"]
    end
```

## Checkpoints = snapshots after every step

```mermaid
flowchart LR
    C1[📸 after parse] --> C2[📸 after prepare] --> C3[📸 after analysts] --> C4[📸 after writer] --> C5[📸 after critic]
```

| Method | What it gives you |
|---|---|
| `graph.get_state(config)` | The latest saved state (used by the `state` command) |
| `graph.get_state_history(config)` | Every snapshot ("time travel") |

## Things memory makes possible here

- Follow-up questions: *"Why did you give that verdict?"*
- **Pausing** for human review ([note 9](09_human_in_the_loop.md)), because a paused graph must be saved somewhere.

> ⚠️ **Gotcha:** old values stay in memory! That's why `prepare_research` resets `report`, `revision_count`, etc. before each new analysis.

| Checkpointer | Stored in | Use for |
|---|---|---|
| `MemorySaver` | RAM (lost on exit) | Learning (this project) |
| `SqliteSaver` | `.db` file | Small apps |
| `PostgresSaver` | Database | Production |
