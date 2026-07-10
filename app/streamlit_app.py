"""
Streamlit front end: embeds/links the Power BI dashboard and hosts the
LLM chat panel.

Run with: streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from llm.chatbot import answer

st.set_page_config(page_title="InsightIQ", layout="wide")
st.title("InsightIQ")

tab_dashboard, tab_chat = st.tabs(["Dashboard", "Ask a question"])

with tab_dashboard:
    st.markdown(
        "Embed the published Power BI report here, e.g. via `st.components.v1.iframe` "
        "with your Power BI \"Publish to web\" embed URL, or link out to the report."
    )
    # st.components.v1.iframe("<power-bi-embed-url>", height=600)

with tab_chat:
    question = st.text_input("Ask a question about the data")
    if question:
        with st.spinner("Thinking..."):
            response = answer(question)
        st.write(response)
