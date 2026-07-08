"""
Retrieval interface used by llm/chatbot.py for the definitional / contextual
side of questions (e.g. "what counts as a repeat customer?").
"""
import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

load_dotenv()

PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./rag/chroma_store")


def get_retriever(k: int = 3):
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectordb = Chroma(persist_directory=PERSIST_DIR, embedding_function=embeddings)
    return vectordb.as_retriever(search_kwargs={"k": k})


def retrieve_context(question: str) -> str:
    retriever = get_retriever()
    docs = retriever.invoke(question)
    return "\n\n".join(d.page_content for d in docs)


if __name__ == "__main__":
    question = "what counts as a repeat customer?"
    print(f"Q: {question}\n")
    print(retrieve_context(question))
