# Technology Stack Deep Dive: Why We Chose What We Chose

For your AI Judge interview, you need to be able to justify *why* you selected specific tools over others. This document provides a deep, technical explanation for every major library and software component used in your project.

---

## 1. Vector Database: ChromaDB (`langchain-chroma`)
**What it is:** An open-source, AI-native, embedded vector database.
**Why it was chosen:**
*   **Strict Adherence to Constraints:** The problem statement explicitly states: *"Must use only the provided support corpus (no live web calls)."* Cloud vector databases like Pinecone, Weaviate Cloud, or Qdrant Cloud would violate this or require complex mock setups. 
*   **Zero-Setup & Embedded:** Chroma runs embedded inside the Python process and persists data locally to a folder (`chroma_db/`). It does not require installing a separate database server or managing Docker containers, making the project highly reproducible for the evaluators grading the ZIP file.
*   **Fast Local Search:** It handles the semantic similarity search (using cosine similarity on vector embeddings) instantly on the local machine, drastically reducing the overall latency of the pipeline compared to making network calls for retrieval.

## 2. Embedding Model: HuggingFace `all-MiniLM-L6-v2` (`sentence-transformers`)
**What it is:** A lightweight transformer model used to convert text into high-dimensional vectors.
**Why it was chosen:**
*   **Local Execution:** Just like the database, embeddings must be generated locally to maintain the strict offline-corpus constraint and maximize speed.
*   **Performance vs. Size:** The `all-MiniLM-L6-v2` model is tiny (around 80MB) and extremely fast to load into memory, yet it provides exceptionally high-quality semantic representations for English text. For a triage corpus (HackerRank, Claude, Visa), it easily differentiates between concepts without the overhead of massive billion-parameter embedding models.

## 3. Orchestration Framework: LangGraph (`langgraph`)
**What it is:** A library for building stateful, multi-actor applications with LLMs, modeling workflows as graphs.
**Why it was chosen:**
*   **Deterministic Routing over Autonomous Chaos:** Standard agents (like LangChain's ReAct agent) are autonomous—they loop continuously, deciding what to do next based purely on LLM reasoning. This is dangerous for a triage system. LangGraph replaces this with a **State Machine**. 
*   **Strict Safety Hand-offs:** Because you defined a specific conditional edge (`triage_route`), you can mathematically guarantee that if the `safety_check_node` flags an issue as high-risk, it will immediately route to the `escalate_node` and skip the `reply_node`. Standard agents might try to hallucinate a reply anyway; LangGraph enforces strict control flow.
*   **State Persistence:** Passing the `AgentState` between nodes makes debugging easy and keeps the context (like the `research_context`) cleanly separated from the active prompt.

## 4. LLM Provider: Google Generative AI (`langchain-google-genai`)
**What it is:** The API interface for Gemini models.
**Why it was chosen:**
*   **Structured Output Natively:** The Gemini API natively supports returning structured data that adheres to a JSON schema (which you map via Pydantic). This drastically reduces parsing errors.
*   **Tool Calling:** The models natively understand when and how to invoke the `search_support_docs` tool, passing the correct `query` and `domain` parameters based on the prompt instructions.

## 5. Schema Validation: Pydantic (`pydantic`)
**What it is:** A data validation library for Python that uses type hints.
**Why it was chosen:**
*   **Guaranteed CSV Schema Matching:** The hackathon requires outputting exactly five columns (`status`, `product_area`, `response`, `justification`, `request_type`) with strictly defined enum values (e.g., status *must* be `replied` or `escalated`). 
*   **Eliminating Brittle Parsing:** Prompting an LLM to "return JSON" often results in trailing commas, missing keys, or markdown wrappers (`````json ... `````) that crash automated graders. By using Pydantic via `.with_structured_output()`, the LLM is forced at the API level to strictly conform to your Python class definition. If it fails, Pydantic catches it immediately rather than corrupting the CSV.

## 6. Resilience & Retry Logic: Tenacity (`tenacity`)
**What it is:** A general-purpose retrying library.
**Why it was chosen:**
*   **Handling Rate Limits Elegantly:** When running a large batch process over hundreds of CSV rows, you are guaranteed to hit `429 Too Many Requests` or `503 Service Unavailable` API errors. 
*   **Exponential Backoff:** Tenacity allows the script to catch these transient errors, pause the specific worker, and wait an exponentially increasing amount of time (`wait_exponential(multiplier=2, min=10, max=120)`) before trying again. This ensures maximum throughput without crashing the whole application, which is a massive engineering "green flag" for judges.

## 7. Concurrency: Asyncio (`asyncio`)
**What it is:** Python's standard library for concurrent code.
**Why it was chosen:**
*   **I/O Bound Speedup:** LLM calls and database queries are purely I/O bound (waiting for network or disk). Running them sequentially (a `for` loop) would take hours. Asyncio allows multiple tickets to be processed simultaneously.
*   **Throttling:** Using `asyncio.Semaphore(batch_size)` prevents the script from launching 500 concurrent requests instantly (which would instantly trigger a permanent ban or rate limit from the API provider). It creates a smooth, controlled pipeline.

## 8. Data Manipulation: Pandas (`pandas`)
**What it is:** The industry-standard data analysis library.
**Why it was chosen:**
*   **Robust I/O:** Reading the `support_tickets.csv` and writing the `output.csv` requires handling missing data (NaNs), differing encodings, and string casting. Pandas handles all of this cleanly out of the box, allowing you to focus on the LLM logic rather than writing complex Python `csv` module parsers.
