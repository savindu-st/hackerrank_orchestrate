# HackerRank Orchestrate — Support Triage Agent (Optimized Gemma 4 Edition)

## Approach Overview

This solution implements a high-performance, resilient support agent designed to handle high-volume ticket processing across multiple domains (HackerRank, Claude, Visa). 

### Architecture & Design Patterns
- **LangGraph Orchestration**: Uses a state-based graph to separate classification, research, and response generation, ensuring a deterministic and audit-ready workflow.
- **Resource Reuse Strategy**: Optimized for throughput by reusing LLM instances and structured output wrappers across the entire session, eliminating redundant initialization overhead.
- **High-Performance Concurrency**: Replaces rigid batching with an **Asynchronous Semaphore Model**. This allows for fluid, parallel processing that maintains maximum utilization of API rate limits without blocking on slow individual tickets.
- **Smart Staggering**: Implements a calculated stagger delay between tasks to stay safely within burst rate limits while maintaining high average throughput.
- **Grounded RAG (Retriever-Augmented Generation)**: All responses are strictly synthesized from a local ChromaDB index built from the official support corpus. The search tool is fully asynchronous, preventing event-loop stalls during IO-bound vector searches.
- **Context Caching**: Extracted research documentation is cached within the `AgentState`, preventing redundant parsing and formatting between decision-making and response-generation nodes.

## Setup

1. **Environment Setup**:
   Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configuration**:
   Copy `.env.example` to `.env` and provide your `GOOGLE_API_KEY`.
   The agent is configured to use `models/gemma-4-31b-it` by default.

3. **Initialize the Knowledge Base**:
   Run the retriever to build the local ChromaDB index:
   ```bash
   python retriever.py
   ```

## Usage

Run the agent on the support ticket dataset:
```bash
python main.py --input ../support_tickets/support_tickets.csv --output ../support_tickets/output.csv --batch_size 5 --delay 40
```

### Advanced Options:
- `--batch_size N` (Default: `10`): Max number of concurrent tickets to process (managed by Semaphore).
- `--delay N` (Default: `65`): Average seconds between ticket starts (used to calculate stagger). 
  *Example: With `--batch_size 5 --delay 40`, the agent will start a new ticket roughly every 8 seconds, maintaining 5 active workers.*

## Output Schema

The agent generates a grading-ready `output.csv` with the following columns:
| Column | Description |
|--------|-------------|
| `status` | `replied`, `escalated`, or `failed` |
| `product_area` | Categorized domain (e.g., `billing`, `security`, `screen`) |
| `response` | Professional, corpus-grounded user-facing answer |
| `justification` | Technical rationale for the triage decision |
| `request_type` | `product_issue`, `feature_request`, `bug`, or `invalid` |
