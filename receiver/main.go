package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	amqp "github.com/rabbitmq/amqp091-go"
)

// verifySignature checks if the payload was actually sent by GitHub
func verifySignature(secret []byte, signatureHeader string, body []byte) bool {
	const signaturePrefix = "sha256="
	if len(signatureHeader) < len(signaturePrefix) || signatureHeader[:len(signaturePrefix)] != signaturePrefix {
		return false
	}

	// Compute our own HMAC using the secret and the body
	mac := hmac.New(sha256.New, secret)
	mac.Write(body)
	expectedMAC := mac.Sum(nil)
	expectedSignature := signaturePrefix + hex.EncodeToString(expectedMAC)

	// hmac.Equal prevents timing attacks (better than standard string comparison)
	return hmac.Equal([]byte(signatureHeader), []byte(expectedSignature))
}

func main() {
	err := godotenv.Load("../.env")
	if err != nil {
		log.Println("Warning: No .env file found")
	}

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

	q, err := ch.QueueDeclare(
		"github_webhooks", true, false, false, false, nil,
	)
	if err != nil {
		log.Fatalf("Failed to declare a queue: %v", err)
	}

	router := gin.Default()

	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "healthy", "service": "receiver"})
	})

	router.POST("/webhook", func(c *gin.Context) {
		// 1. Read the body
		body, err := c.GetRawData()
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Cannot read body"})
			return
		}

		// 2. Security Check: Validate the GitHub Signature
		secret := os.Getenv("GITHUB_WEBHOOK_SECRET")
		signatureHeader := c.GetHeader("X-Hub-Signature-256")
		
		if secret != "" {
			if !verifySignature([]byte(secret), signatureHeader, body) {
				log.Println("SECURITY ALERT: Invalid webhook signature detected and blocked.")
				c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid signature"})
				return
			}
		} else {
			log.Println("Warning: GITHUB_WEBHOOK_SECRET is not set. Running in insecure mode.")
		}

		// 3. Queue the Event
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		err = ch.PublishWithContext(ctx,
			"", q.Name, false, false,
			amqp.Publishing{
				ContentType:  "application/json",
				DeliveryMode: amqp.Persistent,
				Body:         body,
			})

		if err != nil {
			log.Printf("Failed to publish a message: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to queue event"})
			return
		}

		log.Println("Successfully verified and queued webhook event")
		c.JSON(http.StatusOK, gin.H{"message": "Event queued successfully"})
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("Receiver started on port %s...", port)
	router.Run(":" + port)
}