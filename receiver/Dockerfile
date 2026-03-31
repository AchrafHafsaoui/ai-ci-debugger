# /receiver/Dockerfile

# Stage 1: Build the Go binary
FROM golang:1.26-alpine AS builder
WORKDIR /app

# Copy dependency files and download
COPY go.mod go.sum ./
RUN go mod download

# Copy source code and build
COPY . .
RUN go build -o main .

# Stage 2: Create the tiny production image
FROM alpine:latest
WORKDIR /app

# Copy only the compiled binary from Stage 1
COPY --from=builder /app/main .

EXPOSE 8080
CMD ["./main"]