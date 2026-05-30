import os
import logging
import json
from typing import Literal
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from schema import AgentState, SupportTicket, SafetyCheckDecision, FinalOutput
from prompts import CLASSIFIER_PROMPT, SAFETY_CHECK_PROMPT, RESPONSE_GENERATOR_PROMPT, ESCALATE_GENERATOR_PROMPT
from tools import search_support_docs

load_dotenv(override=True)

logger = logging.getLogger(__name__)

# ── API Key + Model Setup ────────────────────────────────────────────────
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEYS", "").split(",")[0].strip()
MODEL_NAME = os.getenv("MODEL_NAME") or os.getenv("MODEL_NAMES", "models/gemma-4-31b-it").split(",")[0].strip()

# Initialize LLMs once to reuse them
_base_llm = ChatGoogleGenerativeAI(
    model=MODEL_NAME,
    google_api_key=API_KEY,
    temperature=0,
    max_retries=2,
)

# Bind tools to a specialized version for the classifier
_classifier_llm = _base_llm.bind_tools([search_support_docs])

# Structured LLMs for different tasks
_safety_structured_llm = _base_llm.with_structured_output(SafetyCheckDecision)
_reply_structured_llm = _base_llm.with_structured_output(FinalOutput)
_escalate_structured_llm = _base_llm.with_structured_output(FinalOutput)


# ── Retry config ──────────────────────────────────────────────────────────
RETRY_KWARGS = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=10, max=120),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def _get_llm(temperature=0):
    """Return the global LLM instance. Note: temperature is currently fixed to 0 for efficiency."""
    return _base_llm


def _extract_research_context(messages: list) -> str:
    """Extract and format text content from tool call results.
    
    Parses the structured JSON output from search_support_docs into a 
    clean, readable list of sources and content for the LLM.
    """
    context_parts = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            try:
                data = json.loads(msg.content)
                if data.get("status") == "success" and "artifacts" in data:
                    for doc in data["artifacts"]:
                        source = doc.get("source", "Unknown")
                        domain = doc.get("domain", "unknown")
                        content = doc.get("content", "")
                        context_parts.append(f"### Source: {source} (Domain: {domain})\n{content}")
                else:
                    context_parts.append(f"[Search Tool Note]: {data.get('summary', 'No content')}")
            except Exception:
                # Fallback for non-JSON or malformed tool output
                context_parts.append(f"[Retrieved Documentation]\n{msg.content}")
        
        elif isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            context_parts.append(f"### Agent Analysis\n{msg.content}")
    
    return "\n\n---\n\n".join(context_parts) if context_parts else "No documentation retrieved."


def classifier_node(state: AgentState):
    @retry(**RETRY_KWARGS)
    def _invoke_classifier():
        ticket = state["ticket"]
        sys_msg = SystemMessage(content=CLASSIFIER_PROMPT.format(
            issue=ticket.issue, subject=ticket.subject, company=ticket.company
        ))
        
        # We don't force a domain filter here to allow the LLM to decide, 
        # but we provide the company context in the prompt.
        human_msg = HumanMessage(content=f"Please research this ticket: {ticket.issue}")
        messages = [sys_msg, human_msg] + state["messages"]
        return _classifier_llm.invoke(messages)

    response = _invoke_classifier()
    return {"messages": [response]}


def should_continue(state: AgentState) -> Literal["tools", "safety_check"]:
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return "safety_check"


def safety_check_node(state: AgentState):
    # Extract research context once and store it in the state
    research_context = _extract_research_context(state["messages"])

    @retry(**RETRY_KWARGS)
    def _invoke_safety():
        ticket = state["ticket"]
        
        sys_msg = SystemMessage(content=SAFETY_CHECK_PROMPT.format(
            issue=ticket.issue, subject=ticket.subject, company=ticket.company
        ))
        human_msg = HumanMessage(content=f"""Review this ticket and the research gathered below.

Ticket: {ticket.issue}

Research Context:
{research_context}

Based on the above, decide whether to REPLY or ESCALATE. Provide your decision, justification, request_type, and product_area.""")
        
        return _safety_structured_llm.invoke([sys_msg, human_msg])

    decision = _invoke_safety()
    logging.info(f"Safety Check Decision: {decision.decision} | Justification: {decision.justification}")

    return {
        "triage_decision": decision.decision,
        "request_type": decision.request_type,
        "product_area": decision.product_area,
        "research_context": research_context
    }


def triage_route(state: AgentState) -> Literal["reply_node", "escalate_node"]:
    if state.get("triage_decision") == "ESCALATE":
        return "escalate_node"
    return "reply_node"


def reply_node(state: AgentState):

    @retry(**RETRY_KWARGS)
    def _invoke_reply():
        ticket = state["ticket"]
        research_context = state.get("research_context", "")
        
        sys_msg = SystemMessage(content=RESPONSE_GENERATOR_PROMPT.format(
            issue=ticket.issue, subject=ticket.subject, company=ticket.company
        ))
        human_msg = HumanMessage(content=f"""Write a helpful response for this ticket using ONLY the documentation below.

Ticket: {ticket.issue}

Documentation:
{research_context}

Provide your response, justification, status, product_area, and request_type.""")
        
        return _reply_structured_llm.invoke([sys_msg, human_msg])

    output = _invoke_reply()
    output.status = "replied"
    output.request_type = state["request_type"]
    output.product_area = state["product_area"]

    return {"final_output": output}


def escalate_node(state: AgentState):
    @retry(**RETRY_KWARGS)
    def _invoke_escalate():
        ticket = state["ticket"]
        research_context = state.get("research_context", "")
        
        sys_msg = SystemMessage(content=ESCALATE_GENERATOR_PROMPT.format(
            issue=ticket.issue, subject=ticket.subject, company=ticket.company
        ))
        human_msg = HumanMessage(content=f"""This ticket is being escalated. Write a polite escalation response.

Ticket: {ticket.issue}

Context gathered:
{research_context}

Provide your response, justification, status, product_area, and request_type.""")
        
        return _escalate_structured_llm.invoke([sys_msg, human_msg])

    output = _invoke_escalate()
    output.status = "escalated"
    output.request_type = state["request_type"]
    output.product_area = state["product_area"]

    return {"final_output": output}



# Build the LangGraph workflow
workflow = StateGraph(AgentState)

workflow.add_node("classifier_node", classifier_node)
tool_node = ToolNode(tools=[search_support_docs])
workflow.add_node("tools", tool_node)
workflow.add_node("safety_check", safety_check_node)
workflow.add_node("reply_node", reply_node)
workflow.add_node("escalate_node", escalate_node)

workflow.add_edge(START, "classifier_node")
workflow.add_conditional_edges("classifier_node", should_continue)
workflow.add_edge("tools", "classifier_node")
workflow.add_conditional_edges("safety_check", triage_route)
workflow.add_edge("reply_node", END)
workflow.add_edge("escalate_node", END)

app = workflow.compile()
