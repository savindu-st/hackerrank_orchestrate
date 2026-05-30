
# HackerRank Orchestrate Hackathon: Support Triage Agent

## Project Overview

The objective of this project is to build and deploy a terminal-based AI support triage agent for the HackerRank Orchestrate hackathon. The agent's core responsibility is to ingest incoming support tickets, classify them by product area and request type, perform grounded retrieval from a local markdown corpus, and finally decide whether to auto-reply to the user or escalate the ticket to a human agent.

## Technology Stack

- **Language:** Python
- **State Management:** LangGraph
- **LLM / Generation:** Google Gemini (`gemini-3.1-pro-high` / `langchain-google-genai`)
- **Retrieval Augmented Generation (RAG):**
  - **Vector Database:** ChromaDB (`langchain-chroma`)
  - **Embeddings:** HuggingFace `all-MiniLM-L6-v2` (`langchain-huggingface`, `sentence-transformers`)
  - **Text Splitting:** `MarkdownTextSplitter`
- **Data Processing:** `pandas`
- **Concurrency:** `asyncio` for asynchronous batch processing of tickets.

## Progress and Architecture

### 1. Vector Database Construction (`retriever.py`)
- We built an indexing script that reads all markdown files from the `data/` directory.
- The text is chunked using a `MarkdownTextSplitter`.
- The chunks are embedded using a local HuggingFace sentence transformer model (`all-MiniLM-L6-v2`).
- The vector store is persisted locally using ChromaDB in the `code/chroma_db` directory.
- *Issue resolved:* Fixed environment dependency errors by adding `sentence-transformers` and `langchain-chroma` to `requirements.txt` and ensuring `retriever.py` is run from the correct directory (`code/`, not `venv/`).

### 2. State Management & Agent Logic (`agent.py` & `schema.py`)
- **State:** We use LangGraph to manage the agent's state, tracking the `ticket`, `messages`, `triage_decision`, `request_type`, and `product_area`.
- **Classification:** The agent first evaluates the ticket to determine its nature (e.g., bug, feature request, general inquiry) and its related product area.
- **Retrieval:** If grounded knowledge is required to resolve the ticket, the agent queries the local ChromaDB vector store.
- **Decision:** The final node determines the action to take:
  - **Reply:** Provide a grounded, accurate response to the user.
  - **Escalate:** Pass the ticket to human support if it cannot be resolved confidently or falls outside the AI's capabilities.
- **Structured Output:** The agent ensures its final output conforms to strict guidelines (status, product_area, response, justification, request_type).

### 3. Asynchronous Processing pipeline (`main.py`)
- Designed to ingest a batch of support tickets from a CSV file using `pandas`.
- Implemented `asyncio.Semaphore` and `asyncio.gather` to concurrently process multiple tickets through the LangGraph agent, improving throughput.
- Added comprehensive error handling and logging (both to console and a local `log.txt` file per the competition's requirements).
- Automatically handles fallback outputs in case of internal processing failures or LLM generation errors (e.g., exhaustion of capacity).

## Next Steps
- Verify the accuracy of the vector DB retrieval by running test queries against `chroma_db`.
- Run the full pipeline (`main.py`) against a sample batch of tickets in `support_tickets/` to ensure end-to-end functionality.
- Evaluate the agent's classification and response generation accuracy against the hackathon evaluation criteria.
- Refine system prompts in `prompts.py` to handle edge cases and improve compliance with expected output schemas.
