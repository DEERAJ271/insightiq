"""
Hybrid chatbot: routes a question to NL2SQL (for numeric/warehouse questions)
and/or RAG (for definitional/contextual questions), then asks Claude to
compose a final answer.

TODO (good Claude Code task): replace the naive keyword router with a
Claude-based classifier call, and support questions that need BOTH paths
(e.g. "what's our repeat customer rate, and what counts as repeat?").
"""
import os
from anthropic import Anthropic
from dotenv import load_dotenv

from llm.nl2sql import answer_numeric_question
from rag.query_engine import retrieve_context

load_dotenv()

client = Anthropic()
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

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

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system="You are a data analyst assistant. Answer using only the provided context. Be concise.",
        messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
    )
    return response.content[0].text


if __name__ == "__main__":
    print(answer("What is the average order value by product category?"))
