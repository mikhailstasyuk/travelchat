# Makefile for containerized app deployment

# Variables
DOCKER_COMPOSE = docker-compose
DOCKER_COMPOSE_SIMPLE = docker-compose -f docker-compose.simple.yml
APP_NAME = myapp
ENV_FILE = .env

# Colors for output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

.PHONY: help build up down restart logs clean test dev prod status health shell

# Default target
help: ## Show this help message
	@echo "$(GREEN)Available commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'

# Environment setup
setup: ## Initial setup - copy env file and create directories
	@echo "$(GREEN)Setting up environment...$(NC)"
	@if [ ! -f $(ENV_FILE) ]; then \
		cp .env.example $(ENV_FILE); \
		echo "$(YELLOW)Created $(ENV_FILE) from .env.example. Please update it with your values.$(NC)"; \
	fi
	@mkdir -p weaviate_data

# Build commands
build: ## Build all Docker images
	@echo "$(GREEN)Building Docker images...$(NC)"
	$(DOCKER_COMPOSE) build || $(DOCKER_COMPOSE_SIMPLE) build

build-simple: ## Build using simple compose file
	@echo "$(GREEN)Building Docker images (simple)...$(NC)"
	$(DOCKER_COMPOSE_SIMPLE) build

build-no-cache: ## Build all Docker images without cache
	@echo "$(GREEN)Building Docker images without cache...$(NC)"
	$(DOCKER_COMPOSE) build --no-cache || $(DOCKER_COMPOSE_SIMPLE) build --no-cache

# Deployment commands
up: setup ## Start all services
	@echo "$(GREEN)Starting all services...$(NC)"
	$(DOCKER_COMPOSE) up -d || $(DOCKER_COMPOSE_SIMPLE) up -d

dev: setup ## Start services in development mode with logs
	@echo "$(GREEN)Starting services in development mode...$(NC)"
	$(DOCKER_COMPOSE) up || $(DOCKER_COMPOSE_SIMPLE) up

prod: setup build ## Deploy in production mode
	@echo "$(GREEN)Deploying in production mode...$(NC)"
	$(DOCKER_COMPOSE) up -d --build || $(DOCKER_COMPOSE_SIMPLE) up -d --build

# Simple deployment (fallback for older docker-compose versions)
up-simple: setup ## Start all services using simple compose file
	@echo "$(GREEN)Starting all services (simple mode)...$(NC)"
	$(DOCKER_COMPOSE_SIMPLE) up -d

dev-simple: setup ## Start services in development mode using simple compose file
	@echo "$(GREEN)Starting services in development mode (simple)...$(NC)"
	$(DOCKER_COMPOSE_SIMPLE) up

prod-simple: setup build-simple ## Deploy using simple compose file
	@echo "$(GREEN)Deploying in production mode (simple)...$(NC)"
	$(DOCKER_COMPOSE_SIMPLE) up -d --build

# Sequential startup (recommended)
start-sequential: setup build-simple ## Start services one by one with health checks
	@echo "$(GREEN)Starting services sequentially...$(NC)"
	@chmod +x start_services.sh
	./start_services.sh

down: ## Stop and remove all services
	@echo "$(GREEN)Stopping all services...$(NC)"
	$(DOCKER_COMPOSE) down

restart: ## Restart all services
	@echo "$(GREEN)Restarting all services...$(NC)"
	$(DOCKER_COMPOSE) restart

# Individual service commands
up-weaviate: ## Start only Weaviate
	$(DOCKER_COMPOSE) up -d weaviate

up-api: ## Start only API service
	$(DOCKER_COMPOSE) up -d api

up-streamlit: ## Start only Streamlit service
	$(DOCKER_COMPOSE) up -d streamlit

# Monitoring commands
logs: ## Show logs for all services
	$(DOCKER_COMPOSE) logs -f

logs-api: ## Show logs for API service
	$(DOCKER_COMPOSE) logs -f api

logs-streamlit: ## Show logs for Streamlit service
	$(DOCKER_COMPOSE) logs -f streamlit

logs-weaviate: ## Show logs for Weaviate service
	$(DOCKER_COMPOSE) logs -f weaviate

status: ## Show status of all services
	@echo "$(GREEN)Service Status:$(NC)"
	$(DOCKER_COMPOSE) ps

health: ## Check health of all services
	@echo "$(GREEN)Health Check:$(NC)"
	@echo "Weaviate: $(curl -s -o /dev/null -w "%%{http_code}" http://localhost:8080/v1/.well-known/ready 2>/dev/null || echo "DOWN")"
	@echo "API: $(curl -s -o /dev/null -w "%%{http_code}" http://localhost:8000/health 2>/dev/null || echo "DOWN - trying root endpoint")"
	@if [ "$(curl -s -o /dev/null -w "%%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")" = "000" ]; then \
		echo "API Root: $(curl -s -o /dev/null -w "%%{http_code}" http://localhost:8000/ 2>/dev/null || echo "DOWN")"; \
	fi
	@echo "Streamlit: $(curl -s -o /dev/null -w "%%{http_code}" http://localhost:8501 2>/dev/null || echo "DOWN")"

# Debug commands
debug: ## Show container network info and logs
	@echo "$(GREEN)Container Status:$(NC)"
	$(DOCKER_COMPOSE_SIMPLE) ps
	@echo "\n$(GREEN)Network Information:$(NC)"
	docker network ls | grep travelchat || echo "No travelchat network found"
	@echo "\n$(GREEN)Container IPs:$(NC)"
	@for container in $($(DOCKER_COMPOSE_SIMPLE) ps -q); do \
		name=$(docker inspect $container --format '{{.Name}}' | sed 's/\///'); \
		ip=$(docker inspect $container --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'); \
		echo "$name: $ip"; \
	done

debug-logs: ## Show recent logs for all services
	@echo "$(GREEN)Recent API logs:$(NC)"
	$(DOCKER_COMPOSE_SIMPLE) logs --tail=10 api
	@echo "\n$(GREEN)Recent Streamlit logs:$(NC)"
	$(DOCKER_COMPOSE_SIMPLE) logs --tail=10 streamlit
	@echo "\n$(GREEN)Recent Weaviate logs:$(NC)"
	$(DOCKER_COMPOSE_SIMPLE) logs --tail=10 weaviate

test-network: ## Test network connectivity between containers
	@echo "$(GREEN)Testing network connectivity:$(NC)"
	@echo "From API container to Weaviate:"
	$(DOCKER_COMPOSE_SIMPLE) exec api curl -s http://weaviate:8080/v1/.well-known/ready || echo "Failed to connect to Weaviate"
	@echo "From Streamlit container to API:"
	$(DOCKER_COMPOSE_SIMPLE) exec streamlit curl -s http://api:8000/health || echo "Failed to connect to API"
	@echo "From Streamlit container to API root:"
	$(DOCKER_COMPOSE_SIMPLE) exec streamlit curl -s http://api:8000/ || echo "Failed to connect to API root"

test-network-python: ## Run Python network test from containers
	@echo "$(GREEN)Running Python network test from API container:$(NC)"
	$(DOCKER_COMPOSE_SIMPLE) exec api python debug_network.py
	@echo "\n$(GREEN)Running Python network test from Streamlit container:$(NC)"
	$(DOCKER_COMPOSE_SIMPLE) exec streamlit python debug_network.py

# Development commands
shell: ## Open shell in API container
	$(DOCKER_COMPOSE) exec api /bin/bash

shell-streamlit: ## Open shell in Streamlit container
	$(DOCKER_COMPOSE) exec streamlit /bin/bash

# Testing commands
test: ## Run tests in container
	@echo "$(GREEN)Running tests...$(NC)"
	$(DOCKER_COMPOSE) exec api python -m pytest tests/ -v

test-local: ## Run tests locally (requires local Python env)
	@echo "$(GREEN)Running tests locally...$(NC)"
	python -m pytest tests/ -v

# Maintenance commands
clean: ## Clean up containers, networks, and volumes
	@echo "$(GREEN)Cleaning up...$(NC)"
	$(DOCKER_COMPOSE) down -v --remove-orphans
	docker system prune -f

clean-all: ## Clean up everything including images
	@echo "$(RED)Cleaning up everything (including images)...$(NC)"
	$(DOCKER_COMPOSE) down -v --remove-orphans
	docker system prune -af
	docker volume rm $(shell docker volume ls -q | grep $(APP_NAME)) 2>/dev/null || true

# Data management
backup-data: ## Backup Weaviate data
	@echo "$(GREEN)Backing up Weaviate data...$(NC)"
	@mkdir -p backups
	docker run --rm -v $(shell pwd)/weaviate_data:/source -v $(shell pwd)/backups:/backup alpine tar czf /backup/weaviate-backup-$(shell date +%Y%m%d-%H%M%S).tar.gz -C /source .

restore-data: ## Restore Weaviate data (usage: make restore-data BACKUP=filename.tar.gz)
	@if [ -z "$(BACKUP)" ]; then \
		echo "$(RED)Please specify BACKUP file: make restore-data BACKUP=filename.tar.gz$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Restoring Weaviate data from $(BACKUP)...$(NC)"
	$(DOCKER_COMPOSE) down
	docker run --rm -v $(shell pwd)/weaviate_data:/target -v $(shell pwd)/backups:/backup alpine tar xzf /backup/$(BACKUP) -C /target
	$(DOCKER_COMPOSE) up -d

# URLs for easy access
urls: ## Show service URLs
	@echo "$(GREEN)Service URLs:$(NC)"
	@echo "  API:       http://localhost:8000"
	@echo "  Streamlit: http://localhost:8501"
	@echo "  Weaviate:  http://localhost:8080"

# Quick development workflow
quick-start: build up urls ## Build, start services, and show URLs

# Production deployment
deploy: prod health ## Full production deployment with health check
	@echo "$(GREEN)Deployment complete!$(NC)"
