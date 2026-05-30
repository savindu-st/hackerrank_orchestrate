import os
from langchain_text_splitters import MarkdownTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

def get_domain(filepath):
    """Infer the support domain from the filepath."""
    parts = filepath.replace("\\", "/").split("/")
    for domain in ["hackerrank", "claude", "visa"]:
        if domain in parts:
            return domain
    return "general"

def build_vector_db():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
    db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "chroma_db"))
    
    docs = []
    # Read all markdown files
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".md"):
                filepath = os.path.join(root, file)
                domain = get_domain(filepath)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    docs.append({
                        "page_content": content, 
                        "metadata": {
                            "source": filepath,
                            "domain": domain
                        }
                    })
                    
    print(f"Found {len(docs)} markdown files.")
    
    splitter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=100)
    
    texts = []
    metadatas = []
    for d in docs:
        chunks = splitter.split_text(d["page_content"])
        texts.extend(chunks)
        metadatas.extend([d["metadata"]] * len(chunks))
        
    print(f"Split into {len(texts)} chunks.")
    
    print("Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    print("Building ChromaDB...")
    vectorstore = Chroma.from_texts(
        texts=texts,
        metadatas=metadatas,
        embedding=embeddings,
        persist_directory=db_dir
    )
    print(f"Vector DB built successfully at {db_dir}")

if __name__ == "__main__":
    build_vector_db()
