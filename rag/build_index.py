"""
Builds a Chroma vector index over:
- the warehouse schema (table/column descriptions)
- the business glossary (sql/schema.sql seeds a few terms)
- any analysis write-ups you add to rag/docs/

This index backs the "definitional" side of the chatbot (RAG), separate from
the NL2SQL path used for numeric questions.

TODO (good Claude Code task): auto-generate schema docs by introspecting
Postgres (information_schema) instead of hand-writing SCHEMA_DOCS below.
"""
import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

load_dotenv()

PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./rag/chroma_store")

# Placeholder schema documentation — expand this as the warehouse evolves.
SCHEMA_DOCS = """
fact_orders: one row per order line item. Key measures: price, freight_value,
review_score. Joins to dim_customer, dim_product, dim_seller, dim_date.

dim_customer: customer_id, city, state, country. Use state for regional analysis.

dim_product: product_id, category, weight_g, dimensions. Use category for
product-mix analysis.

dim_date: standard date dimension with year, quarter, month, day_of_week,
is_weekend flags. Join on order_date_key, delivered_date_key, or
estimated_date_key depending on which date matters for the question.

Business terms:
AOV = average order value = total revenue / number of orders.
SLA breach = delivered_date_key > estimated_date_key.
Repeat customer = customer with more than one distinct order_id.
"""


def build_index():
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(SCHEMA_DOCS)
    docs = [Document(page_content=c, metadata={"source": "schema_docs"}) for c in chunks]

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectordb = Chroma.from_documents(docs, embeddings, persist_directory=PERSIST_DIR)
    vectordb.persist()
    print(f"Indexed {len(docs)} chunks into {PERSIST_DIR}")


if __name__ == "__main__":
    build_index()
