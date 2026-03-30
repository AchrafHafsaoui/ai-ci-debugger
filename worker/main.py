import pika
import os
import sys
import json
from dotenv import load_dotenv

# 1. Load Environment Variables
# We look one level up for the .env file at the root
load_dotenv(dotenv_path="../.env")

def process_webhook(ch, method, properties, body):
    """
    This function triggers every time a message is received from RabbitMQ.
    """
    try:
        # Decode the byte string from RabbitMQ into JSON
        data = json.loads(body)
        print(f" [x] Received Webhook Data: {data}")
        
        # TODO: This is where we will add:
        # 1. GitHub API call to get logs
        # 2. Regex parsing to find the error
        # 3. LLM call to suggest a fix
        
        # Acknowledge the message (tells RabbitMQ it's safe to delete it)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(" [✓] Done processing")
        
    except Exception as e:
        print(f" [!] Error processing message: {e}")
        # If it fails, we don't acknowledge, so it stays in the queue

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