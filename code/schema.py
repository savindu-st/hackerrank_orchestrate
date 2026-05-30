from typing import TypedDict, List, Annotated, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
import operator

class SupportTicket(BaseModel):
    issue: str
    subject: str
    company: str

class AgentState(TypedDict):
    ticket: SupportTicket
    messages: Annotated[List[BaseMessage], operator.add]
    triage_decision: Literal["REPLY", "ESCALATE", "PENDING"]
    request_type: str
    product_area: str
    research_context: str
    final_output: "FinalOutput"

class FinalOutput(BaseModel):
    status: Literal["replied", "escalated", "failed"] = Field(description="Must be 'replied', 'escalated', or 'failed'")
    product_area: str = Field(description="The most relevant support category or domain area")
    response: str = Field(description="User-facing answer grounded in the support corpus or an escalation message")
    justification: str = Field(description="Concise explanation of the decision and response")
    request_type: Literal["product_issue", "feature_request", "bug", "invalid"] = Field(description="The best-fit request classification")

class SafetyCheckDecision(BaseModel):
    decision: Literal["REPLY", "ESCALATE"] = Field(description="Whether the ticket is safe to reply to or needs human escalation.")
    justification: str = Field(description="Why this decision was made.")
    request_type: Literal["product_issue", "feature_request", "bug", "invalid"] = Field(description="Classification of the ticket.")
    product_area: str = Field(description="Category or domain of the issue.")
