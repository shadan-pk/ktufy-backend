# Current Implementation (Minimal)

This document summarizes the current deployment-related implementation and how it is wired together.

## Docker server stack (docker-compose)

Services defined in docker-compose.yml:
- backend: FastAPI app running with Gunicorn + Uvicorn workers on internal port 8000
- nginx: reverse proxy on host ports 80/443 routing to backend
- neo4j: graph database with APOC plugin
- redis: cache/queue (reserved for future use)

Persistent volumes:
- uploads_data: /app/uploads
- vector_data: /app/vector_store
- neo4j_data: /data

Health checks:
- backend: GET /health
- neo4j: neo4j status

## Docker image (Dockerfile)

- Multi-stage build (builder + runtime)
- Python 3.11 slim base
- Installs dependencies from requirements.txt
- Runs as non-root user
- Entrypoint: gunicorn main:app (Uvicorn workers)

## Nginx reverse proxy

File: nginx/nginx.conf
- Proxies all requests to backend:8000
- Basic rate limiting: 30 req/sec with burst 20
- Client max body size: 20 MB
- Forwards standard headers (Host, X-Real-IP, X-Forwarded-For, X-Forwarded-Proto)

## Heroku container deploy

Workflow file: .github/workflows/heroku-container-deploy.yml
- Trigger: push to main or manual workflow_dispatch
- Uses Heroku CLI via GitHub Actions
- Builds and pushes container to Heroku Container Registry
- Releases web container to the Heroku app

Required GitHub secrets:
- HEROKU_API_KEY
- HEROKU_APP_NAME

## Workflow summary

Local development:
- Run FastAPI locally (python main.py or uvicorn main:app --reload)
- Use .env for secrets and service config

Production-like (Docker):
- docker compose up -d --build
- Nginx -> backend -> Neo4j/Redis

CI/CD:
- Push to main triggers GitHub Actions
- Heroku container build + release

## References

- Docker guide: DOCKER.md
- Compose file: docker-compose.yml
- Nginx config: nginx/nginx.conf
- Heroku workflow: .github/workflows/heroku-container-deploy.yml
