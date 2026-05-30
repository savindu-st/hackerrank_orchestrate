# `schema.py` Breakdown

Your `schema.py` file is the data foundation of your agent. It defines exactly how data enters the system, how it moves between LangGraph nodes, and how the LLM's final output is structurally guaranteed.

Here is a deep dive into each class, followed by an exact script you can use to explain it in your interview.

---

## 1. The Breakdown

### `SupportTicket` (Pydantic BaseModel)
```python
class SupportTicket(BaseModel):
    issue: str
    subject: str
    company: str
```
**What it does:** This maps the raw rows from `support_tickets.csv` into a clean Python object.
**Why it matters:** Instead of passing raw, loosely-typed dictionaries around your code, `SupportTicket` ensures you always have dot-notation access (`ticket.issue`) and guarantees the data types exist before processing begins.

### `AgentState` (TypedDict for LangGraph)
```python
class AgentState(TypedDict):
    ticket: SupportTicket
    messages: Annotated[List[BaseMessage], operator.add]
    triage_decision: Literal["REPLY", "ESCALATE", "PENDING"]
    request_type: str
    product_area: str
    research_context: str
    final_output: "FinalOutput"
```
**What it does:** This is the global "memory" passed between every node in your LangGraph workflow.
**Why it matters:** 
*   **Reducer Logic:** The `Annotated[..., operator.add]` on `messages` is crucial. It tells LangGraph that when a new message is returned by a node, it should *append* it to the list, not overwrite the existing list. This is how the agent maintains conversation history with the tool node.
*   **State Tracking:** It explicitly tracks the `triage_decision` and `research_context` so that the final generation nodes (`reply_node` / `escalate_node`) have access to the exact rules and documents established by previous nodes.

### `FinalOutput` & `SafetyCheckDecision` (Pydantic Structured Outputs)
```python
class FinalOutput(BaseModel):
    status: Literal["replied", "escalated", "failed"] = Field(...)
    # ... other 4 CSV columns ...
    request_type: Literal["product_issue", "feature_request", "bug", "invalid"] = Field(...)

class SafetyCheckDecision(BaseModel):
    decision: Literal["REPLY", "ESCALATE"] = Field(...)
    # ...
```
**What it does:** These define strict JSON schemas that the Google Gemini API is forced to adhere to.
**Why it matters:** LLMs are naturally non-deterministic text generators. By passing these Pydantic models into `_base_llm.with_structured_output(...)`, you bind the LLM to an exact API contract. 
*   `FinalOutput` perfectly mirrors the 5 columns required by HackerRank's output CSV. The use of `Literal` ensures the LLM can only pick from the exact enum values allowed (e.g., `status` must be `replied` or `escalated`). It physically cannot output "I think we should reply". 

---

## 2. Word-for-Word Interview Script

**Judge:** *"Can you explain how you managed state and data validation across your workflow?"*

**What to say:**
"I centralized all data structures in `schema.py` using Pydantic and Python's TypedDict. 

For the LangGraph state machine, I defined an `AgentState` TypedDict. This acts as the shared memory passed between nodes. A critical part of this is the `messages` list, which uses Python's `operator.add` via LangGraph's `Annotated` type. This acts as a reducer, ensuring that every time a node yields a new LLM or Tool message, it appends to the history rather than overwriting it.

For data validation, I used Pydantic extensively to control the LLM. The evaluation criteria required a strict 5-column CSV output with specific allowed values. Rather than writing complex regex parsers or begging the LLM to format JSON correctly, I defined a `FinalOutput` Pydantic model. I used Python `Literal` types for fields like `status` and `request_type` to enforce enum constraints. I then used Gemini's structured output bindings so the LLM natively returned this exact Pydantic object. This completely eliminated parsing errors and guaranteed my `output.csv` was perfectly formatted for the auto-grader. I used the exact same approach with a `SafetyCheckDecision` model to mathematically force the triage node to return either 'REPLY' or 'ESCALATE', preventing the LLM from waffling."
