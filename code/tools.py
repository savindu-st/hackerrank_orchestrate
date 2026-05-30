from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.tools import tool
import os
from pydantic import BaseModel, Field
from typing import Optional
import json

class SearchInput(BaseModel):
    query: str = Field(description="The search query to look up in the support documentation.")
    domain: Optional[str] = Field(
        default=None, 
        description="The support domain to filter by: 'hackerrank', 'claude', or 'visa'. Improves precision."
    )

db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chroma_db"))

# We delay the initialization until it's actually used, or we can just initialize it globally
_vectorstore = None
_retriever = None

def init_retriever():
    """Warm up the embedding model and initialize the vector store."""
    global _vectorstore, _retriever
    if _retriever is None:
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        _vectorstore = Chroma(persist_directory=db_dir, embedding_function=embeddings)
        _retriever = _vectorstore.as_retriever(search_kwargs={"k": 4})
    return _retriever

@tool("search_support_docs", args_schema=SearchInput)
async def search_support_docs(query: str, domain: Optional[str] = None) -> str:
    """
    Search the multi-domain support documentation for HackerRank, Claude, and Visa.
    Returns the top matching documentation snippets.
    Always use this tool to find policies, instructions, or facts to answer the user's issue.
    """
    try:
        init_retriever()
        
        search_kwargs = {"k": 5}
        if domain and domain.lower() != "none":
            search_kwargs["filter"] = {"domain": domain.lower()}
            
        # Use asynchronous search to avoid blocking
        docs = await _vectorstore.asimilarity_search(query, **search_kwargs)
        
        if not docs:
            return json.dumps({
                "status": "warning", 
                "summary": f"No relevant documents found in domain: {domain or 'all'}.", 
                "next_actions": ["Try a different query or remove domain filter"]
            })
        
        results = []
        for d in docs:
            results.append({
                "source": os.path.basename(d.metadata.get('source', 'Unknown')),
                "content": d.page_content,
                "domain": d.metadata.get('domain', 'unknown')
            })
            
        return json.dumps({
            "status": "success", 
            "summary": f"Found {len(docs)} documents", 
            "artifacts": results
        })
    except Exception as e:
        return json.dumps({
            "status": "error", 
            "summary": "Failed to search docs", 
            "next_actions": ["Retry search"], 
            "error_hint": str(e)
        })
