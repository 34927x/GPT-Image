#!/bin/bash

# Stop and remove existing container if running
echo "🧹 Cleaning up old containers..."
docker stop gpt-image-worker-container 2>/dev/null
docker rm gpt-image-worker-container 2>/dev/null

# Build the image
echo "🔨 Building Docker image..."
docker build -t gpt-image-worker .

# Run the container with hard 350MB memory limit
echo "🚀 Launching container with 350MB RAM limit..."
docker run -d \
  --name gpt-image-worker-container \
  -p 8888:8888 \
  --memory="350m" \
  --memory-swap="350m" \
  --env-file .env \
  gpt-image-worker

echo "📋 Checking container status:"
docker ps | grep gpt-image-worker-container

echo "🔍 Showing logs (press Ctrl+C to exit logs view):"
docker logs -f gpt-image-worker-container
