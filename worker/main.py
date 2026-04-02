import pika
import os
import sys
import json
import requests 
import re 
import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from openai import OpenAI  

load_dotenv(dotenv_path="../.env")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DB_URL = os.getenv("DATABASE_URL")

# We use the OpenAI library, but point it at Groq's free servers
ai_client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1" 
)

print(" [~] Loading local embedding model (this takes a few seconds)...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def get_db_connection():
    """Establishes a connection to PostgreSQL and registers the vector type."""
    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    return conn

def find_similar_failures(error_text, repo_name):
    """Searches the database for past failures that look mathematically similar to this one."""
    print(" [~] Searching long-term memory for similar past failures...")
    try:
        query_embedding = embedding_model.encode(error_text).tolist()
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Using Cosine Distance to find the closest matching vector
        cur.execute("""
            SELECT error_snippet, ai_diagnosis, 1 - (embedding <=> %s::vector) AS similarity
            FROM failure_history
            WHERE repo_name = %s
            ORDER BY embedding <=> %s::vector
            LIMIT 1;
        """, (query_embedding, repo_name, query_embedding))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        # Only return it if it's a reasonably close match (similarity > 0.8)
        if result and result[2] > 0.8:
            print(f" [i] Found a historical match! (Similarity: {result[2]:.2f})")
            return {"error": result[0], "diagnosis": result[1]}
        return None
    except Exception as e:
        print(f" [!] Database search failed: {e}")
        return None

def save_failure_to_db(repo_name, commit_sha, error_snippet, ai_diagnosis):
    """Saves the failure and the AI's diagnosis into PostgreSQL for future reference."""
    print(" [~] Saving failure to long-term memory...")
    try:
        embedding = embedding_model.encode(error_snippet).tolist()
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO failure_history (repo_name, commit_sha, error_snippet, ai_diagnosis, embedding)
            VALUES (%s, %s, %s, %s, %s)
        """, (repo_name, commit_sha, error_snippet, ai_diagnosis, embedding))
        
        conn.commit()
        cur.close()
        conn.close()
        print(" [✓] Successfully committed to memory.")
    except Exception as e:
        print(f" [!] Failed to save to database: {e}")

def comment_already_exists(repo_full_name, commit_sha):
    """Checks if the AI Debugger has already commented on this commit."""
    print(" [~] Checking for existing AI comments...")
    url = f"https://api.github.com/repos/{repo_full_name}/commits/{commit_sha}/comments"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            comments = response.json()
            for comment in comments:
                # We look for our unique header signature to prevent duplicates
                if "## 🤖 AI Debugger Diagnosis" in comment.get("body", ""):
                    return True
        return False
    except Exception as e:
        print(f" [!] Error checking comments: {e}")
        return False

def analyze_log_with_ai(clean_logs, commit_diff, historical_context=None, project_context=""):
    """Sends the cleaned log, diff, historical memory, and full project context to the LLM."""
    print(" [~] Sending deep context to AI for analysis...")
    
    user_prompt = f"Here is the failing log:\n\n{clean_logs}\n\n"
    
    if commit_diff:
        user_prompt += f"--- GIT DIFF ---\n{commit_diff}\n\n"
        
    if project_context:
        user_prompt += f"--- PROJECT CONTEXT (Full Files & Manifests) ---\n{project_context}\n\n"
        
    if historical_context:
        user_prompt += f"--- HISTORICAL CONTEXT ---\nA very similar error occurred in the past:\nPast Error:\n{historical_context['error']}\n\nHow we fixed it last time:\n{historical_context['diagnosis']}\n\nPlease use this historical context to inform your current diagnosis.\n"
    
    try:
        response = ai_client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "You are a Senior DevOps Engineer. Analyze the provided CI/CD logs, the code diff, "
                        "and the full file contents (Project Context). Use the manifests (like go.mod or requirements.txt) "
                        "to check for dependency issues. Use the full file contents to understand logic outside the diff. "
                        "Identify the root cause and provide a short, specific, and actionable fix. "
                        "Keep your explanation under 4 sentences."
                    )
                },
                {
                    "role": "user", 
                    "content": user_prompt
                }
            ],
            max_tokens=500,
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Analysis Failed: {e}"

def fetch_workflow_logs(repo_full_name, job_id):
    """Fetches raw logs from GitHub API for a specific job."""
    url = f"https://api.github.com/repos/{repo_full_name}/actions/jobs/{job_id}/logs"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    return None

def sanitize_log(raw_log):
    """Strips timestamps but preserves GitHub Actions formatting tags."""
    cleaned_lines = []
    for line in raw_log.splitlines():
        line = re.sub(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s?', '', line).strip()
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)

def post_github_comment(repo_full_name, commit_sha, comment_body):
    """Posts the AI diagnosis as a comment on the failed commit."""
    print(" [~] Pushing diagnosis to GitHub...")
    url = f"https://api.github.com/repos/{repo_full_name}/commits/{commit_sha}/comments"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    formatted_comment = f"## 🤖 AI Debugger Diagnosis\n\n{comment_body}"
    data = {"body": formatted_comment}
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        print(" [✓] Successfully posted AI diagnosis to GitHub!")
    else:
        print(f" [!] Failed to post comment: {response.status_code} - {response.text}")

def fetch_commit_diff(repo_full_name, commit_sha):
    """Fetches the raw code diff (patch) for the commit that broke the build."""
    print(" [~] Fetching code diff for context...")
    url = f"https://api.github.com/repos/{repo_full_name}/commits/{commit_sha}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff", 
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        print(f" [!] Failed to fetch diff: {response.status_code}")
        return None

def fetch_full_file(repo_full_name, file_path, commit_sha):
    """Fetches the complete content of a specific file at a specific commit."""
    print(f" [~] Fetching full context for {file_path}...")
    url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}?ref={commit_sha}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.raw", # Get raw text
    }
    response = requests.get(url, headers=headers)
    return response.text if response.status_code == 200 else ""

def process_webhook(ch, method, properties, body):
    try:
        payload = json.loads(body)
        action = payload.get("action")
        workflow_job = payload.get("workflow_job", {})
        conclusion = workflow_job.get("conclusion")

        if action == "completed" and conclusion == "failure":
            repo_name = payload["repository"]["full_name"]
            job_id = workflow_job["id"]                    
            commit_sha = workflow_job.get("head_sha")
            
            print(f"\n [!] Detected failure in {repo_name} (Job ID: {job_id})")

            if commit_sha and comment_already_exists(repo_name, commit_sha):
                print(f" [i] AI has already commented on commit {commit_sha[:7]}. Skipping.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            raw_logs = fetch_workflow_logs(repo_name, job_id)
            if raw_logs:
                clean_logs = sanitize_log(raw_logs)
                log_snippet = "\n".join(clean_logs.splitlines()[-50:])
                
                commit_diff = None
                project_context = ""
                
                if commit_sha:
                    commit_diff = fetch_commit_diff(repo_name, commit_sha)
                    
                    # --- NEW: PROJECT CONTEXT EXTRACTION ---
                    # Find all files changed in the diff
                    changed_files = re.findall(r'diff --git a/(.*?) b/', commit_diff)
                    
                    # Fetch dependency manifests for extra context
                    manifests = ["go.mod", "requirements.txt", "package.json", "receiver/Dockerfile"]
                    for manifest in manifests:
                        content = fetch_full_file(repo_name, manifest, commit_sha)
                        if content:
                            project_context += f"--- MANIFEST: {manifest} ---\n{content}\n\n"

                    # Fetch full content for the first 2 changed files to stay within token limits
                    for file_path in changed_files[:2]:
                        content = fetch_full_file(repo_name, file_path, commit_sha)
                        if content:
                            project_context += f"--- FULL FILE CONTENT: {file_path} ---\n{content}\n\n"

                # --- RAG PIPELINE ---
                historical_context = find_similar_failures(log_snippet, repo_name)
                
                ai_suggestion = analyze_log_with_ai(log_snippet, commit_diff, historical_context, project_context)
                
                print("\n==================================================")
                print("AI DEBUGGER DIAGNOSIS:")
                print("==================================================")
                print(ai_suggestion)
                print("==================================================\n")
                
                if commit_sha:
                    post_github_comment(repo_name, commit_sha, ai_suggestion)
                    
                # Save this new experience to memory
                save_failure_to_db(repo_name, commit_sha, log_snippet, ai_suggestion)

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"Error: {e}")

def main():
    url = os.getenv("RABBITMQ_URL")
    connection = pika.BlockingConnection(pika.URLParameters(url))
    channel = connection.channel()
    channel.queue_declare(queue='github_webhooks', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='github_webhooks', on_message_callback=process_webhook)

    print(' [*] Worker waiting for logs. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)