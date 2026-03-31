import pika
import os
import sys
import json
from dotenv import load_dotenv
import requests 

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
            
            logs = fetch_workflow_logs(repo_name, job_id)
            if logs:
                # For now, let's just print the last 20 lines of the log
                log_lines = logs.splitlines()[-20:]
                print("--- LOG SNIPPET ---")
                print("\n".join(log_lines))
                print("--- END LOG ---")
                
                # NEXT STEP: This 'logs' string goes to the AI
            
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"Error: {e}")

def main():
    # 2. Connect to RabbitMQ
    url = os.getenv("RABBITMQ_URL")
    params = pika.URLParameters(url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    # 3. Ensure the queue exists (same settings as Go)
    channel.queue_declare(queue='github_webhooks', durable=True)

    # 4. Set Quality of Service (Don't give this worker more than 1 message at a time)
    channel.basic_qos(prefetch_count=1)

    # 5. Tell RabbitMQ which function handles the messages
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