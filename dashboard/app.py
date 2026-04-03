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

@st.cache_data(ttl=600)
def fetch_all_repos():
    """Fetch a unique list of repositories for the filter dropdown."""
    query = "SELECT DISTINCT repo_name FROM failure_history ORDER BY repo_name ASC;"
    df = pd.read_sql(query, conn)
    return ["All"] + df['repo_name'].tolist()

@st.cache_data(ttl=60)
def fetch_recent_failures(search_query="", repo_filter="All"):
    """Fetch the latest diagnoses with optional filtering."""
    query = """
        SELECT repo_name, commit_sha, error_snippet, ai_diagnosis, created_at 
        FROM failure_history 
        WHERE 1=1
    """
    params = []
    
    if repo_filter != "All":
        query += " AND repo_name = %s"
        params.append(repo_filter)
        
    if search_query:
        # Search in both snippet and diagnosis
        query += " AND (error_snippet ILIKE %s OR ai_diagnosis ILIKE %s)"
        search_pattern = f"%{search_query}%"
        params.append(search_pattern)
        params.append(search_pattern)
        
    query += " ORDER BY created_at DESC LIMIT 100;"
    
    return pd.read_sql(query, conn, params=params)

# --- UI LAYOUT ---
st.title("🤖 AI Debugger Command Center")
st.markdown("Monitor continuous integration failures and AI RAG memory.")

# Fetch Metadata
try:
    stats_df = fetch_basic_stats()
    repo_list = fetch_all_repos()
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

# --- FILTERING SECTION ---
st.subheader("🔍 Search & Filter")
f_col1, f_col2 = st.columns([1, 2])

with f_col1:
    selected_repo = st.selectbox("Filter by Repository", repo_list)

with f_col2:
    search_text = st.text_input("Search Logs or AI Diagnosis", placeholder="e.g. 'psycopg2', 'connection timeout', 'main.py'...")

# Fetch Filtered Data
failures_df = fetch_recent_failures(search_text, selected_repo)

# --- VECTOR MEMORY BANK ---
st.subheader(f"🗄️ Vector Memory Bank ({len(failures_df)} results)")

if not failures_df.empty:
    for index, row in failures_df.iterrows():
        # Format the date for the label
        formatted_date = row['created_at'].strftime("%Y-%m-%d %H:%M")
        
        with st.expander(f"🛑 [{formatted_date}] {row['repo_name']} (Commit: {row['commit_sha'][:7]})"):
            st.caption(f"🕒 **Full Detection Time:** {row['created_at'].strftime('%Y-%m-%d %H:%M:%S')} | **Commit:** `{row['commit_sha']}`")
            
            st.markdown("**Error Snippet:**")
            st.code(row['error_snippet'], language="bash")
            st.markdown("**AI Diagnosis:**")
            st.info(row['ai_diagnosis'])
else:
    st.info("No matching failures found. Try adjusting your search filters.")