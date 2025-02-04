!/bin/bash

echo "Stopping the core-process container..."
docker stop core-process

echo "Removing the core-process container..."
docker rm core-process

echo "Building the Docker images without cache..."
docker compose build --no-cache

echo "Starting the containers..."
docker compose up -d

echo "Following the logs of the core-process container..."
docker logs core-process -f
