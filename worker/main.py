import pika
import os
import sys
import json
import requests 
import re 
from dotenv import load_dotenv
from openai import OpenAI  # <--- NEW: Import the AI library

# Load environment variables
load_dotenv(dotenv_path="../.env")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# NEW: Initialize the AI Client. 
# We use the OpenAI library, but point it at Groq's free servers!
ai_client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1" 
)

def analyze_log_with_ai(clean_logs):
    """Sends the cleaned log to the LLM and asks for a fix."""
    print(" [~] Sending logs to AI for analysis...")
    
    try:
        response = ai_client.chat.completions.create(
            model="llama-3.1-8b-instant", # Groq's blindingly fast open-source model
            messages=[
                {
                    "role": "system", 
                    "content": "You are a Senior DevOps Engineer. Analyze the provided CI/CD failure logs. Identify the exact root cause of the crash, and provide a short, specific, and actionable fix (e.g., a bash command or code change). Keep your explanation under 4 sentences."
                },
                {
                    "role": "user", 
                    "content": f"Here is the failing log:\n\n{clean_logs}"
                }
            ],
            max_tokens=500,
            temperature=0.2 # Keep it analytical and factual, not creative
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

def process_webhook(ch, method, properties, body):
    try:
        payload = json.loads(body)
        
        action = payload.get("action")
        workflow_job = payload.get("workflow_job", {})
        conclusion = workflow_job.get("conclusion")

        if action == "completed" and conclusion == "failure":
            repo_name = payload["repository"]["full_name"]
            job_id = workflow_job["id"]
            
            print(f"\n [!] Detected failure in {repo_name} (Job ID: {job_id})")
            
            raw_logs = fetch_workflow_logs(repo_name, job_id)
            if raw_logs:
                clean_logs = sanitize_log(raw_logs)
                
                # We only send the last 50 lines to the AI to save tokens and context window
                log_snippet = "\n".join(clean_logs.splitlines()[-50:])
                
                # --- THE MAGIC HAPPENS HERE ---
                ai_suggestion = analyze_log_with_ai(log_snippet)
                
                print("\n==================================================")
                print("AI DEBUGGER DIAGNOSIS:")
                print("==================================================")
                print(ai_suggestion)
                print("==================================================\n")
            
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