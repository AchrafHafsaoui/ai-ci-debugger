import streamlit as st
import psycopg2
import pandas as pd
import os
from dotenv import load_dotenv

# Page Config
st.set_page_config(page_title="AI Debugger Command Center", page_icon="🤖", layout="wide")
load_dotenv(dotenv_path="../.env")

DB_URL = os.getenv("DATABASE_URL")

@st.cache_resource
def init_connection():
    """Establish a cached connection to PostgreSQL."""
    return psycopg2.connect(DB_URL)

conn = init_connection()

@st.cache_data(ttl=60) 
def fetch_basic_stats():
    """Fetch high-level metrics."""
    query = """
        SELECT 
            COUNT(*) as total_failures,
            COUNT(DISTINCT repo_name) as unique_repos
        FROM failure_history;
    """
    return pd.read_sql(query, conn)

@st.cache_data(ttl=60)
def fetch_recent_failures():
    """Fetch the latest 100 diagnoses."""
    query = """
        SELECT repo_name, commit_sha, error_snippet, ai_diagnosis 
        FROM failure_history 
        LIMIT 100;
    """
    return pd.read_sql(query, conn)

# --- UI LAYOUT ---
st.title("🤖 AI Debugger Command Center")
st.markdown("Monitor continuous integration failures and AI RAG memory.")

# Fetch Data
try:
    stats_df = fetch_basic_stats()
    failures_df = fetch_recent_failures()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

# --- TOP ROW: METRICS ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Total Failures Diagnosed", value=int(stats_df['total_failures'][0]))
with col2:
    st.metric(label="Monitored Repositories", value=int(stats_df['unique_repos'][0]))
with col3:
    st.metric(label="RAG Engine Status", value="Online 🟢")

st.divider()

# --- VECTOR MEMORY BANK ---
st.subheader("🗄️ Vector Memory Bank (Recent Diagnoses)")

if not failures_df.empty:
    # Create a beautiful, expandable list of failures
    for index, row in failures_df.iterrows():
        with st.expander(f"🛑 {row['repo_name']} (Commit: {row['commit_sha'][:7]})"):
            st.markdown("**Error Snippet:**")
            st.code(row['error_snippet'], language="bash")
            st.markdown("**AI Diagnosis:**")
            st.info(row['ai_diagnosis'])
else:
    st.info("No failures recorded yet. Break some code!")