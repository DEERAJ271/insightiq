"""
Hybrid chatbot: routes a question to NL2SQL (for numeric/warehouse questions)
and/or RAG (for definitional/contextual questions), then asks Claude or a
local Ollama model (whichever LLM_BACKEND selects) to compose a final answer.

TODO (good Claude Code task): replace the naive keyword router with a
Claude-based classifier call, and support questions that need BOTH paths
(e.g. "what's our repeat customer rate, and what counts as repeat?").
"""
import logging
import os
import re
import requests
from anthropic import Anthropic
from dotenv import load_dotenv

from llm.nl2sql import answer_numeric_question, SQLExecutionError, sql_generation_failure_message
from rag.query_engine import retrieve_context

logger = logging.getLogger(__name__)

# Guards against the compose step itself hallucinating a raw SQL statement
# instead of a natural-language answer (a separate failure mode from
# run_query() execution errors, which SQLExecutionError already covers).
RAW_SQL_PATTERN = re.compile(r"^\s*(select|insert|update|delete)\b", re.IGNORECASE)

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
    return any(re.search(rf"\b{re.escape(kw)}\b", q) for kw in NUMERIC_KEYWORDS)


def answer(question: str) -> str:
    if needs_sql(question):
        try:
            _, df = answer_numeric_question(question)
        except SQLExecutionError as e:
            return str(e)
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
        result = response.json()["response"].strip()
    else:
        response = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        result = response.content[0].text

    if RAW_SQL_PATTERN.match(result):
        logger.error(
            "Compose step returned raw SQL instead of a natural-language "
            "answer.\nQuestion: %s\nBackend: %s\nResponse: %s",
            question, LLM_BACKEND, result,
        )
        return sql_generation_failure_message()

    return result


if __name__ == "__main__":
    print(answer("What is the average order value by product category?"))
