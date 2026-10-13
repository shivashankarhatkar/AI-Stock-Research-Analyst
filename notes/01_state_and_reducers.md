# 1. State & Reducers

## State = the shared notebook

Every step (node) **reads** the state and **returns only the parts it changed**. LangGraph merges those changes in and passes the updated state to the next step.

```mermaid
flowchart LR
    S1["state<br/>ticker: ''"] --> N1[parse_request] -- "returns {ticker: 'TCS.NS'}" --> S2["state<br/>ticker: 'TCS.NS'"]
    S2 --> N2[fundamental_analyst] -- "returns {fundamental_analysis: '...'}" --> S3["state<br/>ticker: 'TCS.NS'<br/>fundamental_analysis: '...'"]
```

The shape of the state is declared once with a `TypedDict`, in [state.py](../state.py):

```python
class AgentState(TypedDict, total=False):
    ticker: str
    report: str
    messages: Annotated[list[AnyMessage], add_messages]
    steps_log: Annotated[list[str], operator.add]
```

## Reducers = how updates are merged

| Key declared as | When a node returns a new value… |
|---|---|
| `report: str` (no reducer) | the old value is **overwritten** |
| `Annotated[list, operator.add]` | the new items are **appended** (`old + new`) |
| `Annotated[list, add_messages]` | chat messages are **appended** (or updated by id) |

```mermaid
flowchart LR
    subgraph Overwrite["report: str"]
        A1["'draft 1'"] -- "node returns 'draft 2'" --> A2["'draft 2'"]
    end
    subgraph Append["steps_log: operator.add"]
        B1["['parse']"] -- "node returns ['critic']" --> B2["['parse', 'critic']"]
    end
```

## Why reducers matter

When **parallel** nodes write to the **same key** at the same time, LangGraph needs a reducer to combine them. Without one, you get an `InvalidUpdateError`. In this project all three analysts append to `steps_log` safely because it uses `operator.add`.

> ✅ **Rule:** a node returns a dict of updates. It never edits `state` directly.
