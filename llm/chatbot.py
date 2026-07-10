"""
Hybrid chatbot: routes a question to NL2SQL (for numeric/warehouse questions)
and/or RAG (for definitional/contextual questions), then asks Claude to
compose a final answer.

TODO (good Claude Code task): replace the naive keyword router with a
Claude-based classifier call, and support questions that need BOTH paths
(e.g. "what's our repeat customer rate, and what counts as repeat?").
"""
import os
import requests
from anthropic import Anthropic
from dotenv import load_dotenv

from llm.nl2sql import answer_numeric_question
from rag.query_engine import retrieve_context

load_dotenv()

client = Anthropic()
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

# "anthropic" or "ollama" — defaults to ollama so local dev doesn't spend
# Anthropic credits; set LLM_BACKEND=anthropic when credits are available.
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

SYSTEM_PROMPT = "You are a data analyst assistant. Answer using only the provided context. Be concise."

NUMERIC_KEYWORDS = ["how many", "average", "total", "rate", "revenue", "trend", "count"]


def needs_sql(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in NUMERIC_KEYWORDS)


def answer(question: str) -> str:
    if needs_sql(question):
        _, df = answer_numeric_question(question)
        data_summary = df.to_markdown(index=False) if not df.empty else "No rows returned."
        context = f"Query result:\n{data_summary}"
    else:
        context = retrieve_context(question)

    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

    if LLM_BACKEND == "ollama":
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": f"{SYSTEM_PROMPT}\n\n{user_prompt}",
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


if __name__ == "__main__":
    print(answer("What is the average order value by product category?"))
