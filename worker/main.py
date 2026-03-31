import pika
import os
import sys
import json
from dotenv import load_dotenv
import requests 
import re 

load_dotenv(dotenv_path="../.env")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

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
    else:
        print(f"Failed to fetch logs: {response.status_code}")
        return None

def sanitize_log(raw_log):
    """Strips timestamps to save tokens, but preserves GitHub Actions formatting tags for LLM context."""
    cleaned_lines = []
    
    for line in raw_log.splitlines():
        # ONLY strip the ISO timestamp at the start of the line
        line = re.sub(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s?', '', line)
        
        line = line.strip()
        
        # Keep the line if it's not empty
        if line:
            cleaned_lines.append(line)
            
    return "\n".join(cleaned_lines)

def process_webhook(ch, method, properties, body):
    try:
        payload = json.loads(body)
        
        # We only care about completed jobs that failed
        action = payload.get("action")
        workflow_job = payload.get("workflow_job", {})
        conclusion = workflow_job.get("conclusion")

        if action == "completed" and conclusion == "failure":
            repo_name = payload["repository"]["full_name"]
            job_id = workflow_job["id"]
            
            print(f" [!] Detected failure in {repo_name} (Job ID: {job_id}). Fetching logs...")
            
            raw_logs = fetch_workflow_logs(repo_name, job_id)
            if raw_logs:
                # 1. Pass the raw logs through our new sanitizer
                clean_logs = sanitize_log(raw_logs)
                
                # 2. Print the last 20 lines of the CLEANED log to verify
                log_lines = clean_logs.splitlines()[-20:]
                print("--- CLEANED LOG SNIPPET ---")
                print("\n".join(log_lines))
                print("--- END CLEANED LOG ---")
                
                # NEXT STEP: This 'clean_logs' string goes to the AI
            
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"Error: {e}")

def main():
    # Connect to RabbitMQ
    url = os.getenv("RABBITMQ_URL")
    params = pika.URLParameters(url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    # Ensure the queue exists
    channel.queue_declare(queue='github_webhooks', durable=True)

    # Set Quality of Service
    channel.basic_qos(prefetch_count=1)

    # Tell RabbitMQ which function handles the messages
    channel.basic_consume(queue='github_webhooks', on_message_callback=process_webhook)

    print(' [*] Worker waiting for logs. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)