package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	amqp "github.com/rabbitmq/amqp091-go"
)

func main() {
	// 1. Load Environment Variables (looking up one directory since we run from /receiver)
	err := godotenv.Load("../.env")
	if err != nil {
		log.Println("Warning: No .env file found, falling back to system environment variables")
	}

	// 2. Connect to RabbitMQ
	rabbitURL := os.Getenv("RABBITMQ_URL")
	conn, err := amqp.Dial(rabbitURL)
	if err != nil {
		log.Fatalf("Failed to connect to RabbitMQ: %v", err)
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		log.Fatalf("Failed to open a channel: %v", err)
	}
	defer ch.Close()

	// 3. Declare the Queue (Ensures the queue exists before we send to it)
	q, err := ch.QueueDeclare(
		"github_webhooks", // name
		true,              // durable (survives broker restart)
		false,             // delete when unused
		false,             // exclusive
		false,             // no-wait
		nil,               // arguments
	)
	if err != nil {
		log.Fatalf("Failed to declare a queue: %v", err)
	}

	// 4. Set up the Web Server
	router := gin.Default()

	// Health check endpoint (DevOps best practice)
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy", "service": "receiver"})
	})

	// The actual Webhook Endpoint
	router.POST("/webhook", func(c *gin.Context) {
		// Read the incoming JSON from GitHub
		body, err := c.GetRawData()
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Cannot read body"})
			return
		}

		// Create a timeout context (Don't let the server hang forever)
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		// Publish the raw JSON directly to RabbitMQ
		err = ch.PublishWithContext(ctx,
			"",     // exchange
			q.Name, // routing key (queue name)
			false,  // mandatory
			false,  // immediate
			amqp.Publishing{
				ContentType:  "application/json",
				DeliveryMode: amqp.Persistent, // Saves message to disk
				Body:         body,
			})

		if err != nil {
			log.Printf("Failed to publish a message: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to queue event"})
			return
		}

		log.Println("Successfully received and queued webhook event")
		c.JSON(http.StatusOK, gin.H{"message": "Event queued successfully"})
	})

	// 5. Start the Server
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("Receiver started on port %s...", port)
	router.Run(":" + port)
}