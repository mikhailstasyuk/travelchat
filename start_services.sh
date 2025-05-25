#!/bin/bash
set -e

echo "🚀 Starting services with proper startup sequence..."

# Function to wait for service
wait_for_service() {
    local service_name=$1
    local url=$2
    local max_attempts=30
    local attempt=0

    echo "⏳ Waiting for $service_name at $url..."

    while [ $attempt -lt $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            echo "✅ $service_name is ready!"
            return 0
        fi

        echo "   Attempt $((attempt + 1))/$max_attempts - $service_name not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "❌ $service_name failed to start after $max_attempts attempts"
    return 1
}

# Start Weaviate first
echo "🔧 Starting Weaviate..."
docker-compose -f docker-compose.simple.yml up -d weaviate

# Wait for Weaviate to be ready
wait_for_service "Weaviate" "http://localhost:8080/v1/.well-known/ready"

# Start API
echo "🔧 Starting API..."
docker-compose -f docker-compose.simple.yml up -d api

# Wait for API to be ready
wait_for_service "API" "http://localhost:8000/"

# Start Streamlit
echo "🔧 Starting Streamlit..."
docker-compose -f docker-compose.simple.yml up -d streamlit

# Wait for Streamlit to be ready
wait_for_service "Streamlit" "http://localhost:8501/"

echo "🎉 All services are running!"
echo "   🌐 Weaviate:  http://localhost:8080"
echo "   🚀 API:       http://localhost:8000"
echo "   📊 Streamlit: http://localhost:8501"
