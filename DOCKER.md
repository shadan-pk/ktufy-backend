# KTUfy Backend Docker Guide

This document explains how the Docker setup works and how to run it on any machine.

## What Was Added

- A production-ready Docker image for the backend (Gunicorn + Uvicorn workers)
- A full Docker Compose stack: backend, Nginx, Neo4j, and Redis
- An Nginx reverse proxy config with basic rate limiting
- Persistent volumes for uploads and vector storage

## Files Added or Updated

- Dockerfile: builds the backend image
- .dockerignore: excludes local-only files from the image
- docker-compose.yml: runs the full stack
- nginx/nginx.conf: reverse proxy for the backend
- requirements.txt: includes gunicorn
- README.md: Docker run instructions

## How the Stack Works

- Nginx listens on ports 80 and 443 and forwards traffic to the backend service.
- The backend runs on port 8000 inside the Docker network.
- Neo4j and Redis run as containers and are reachable from the backend by service name.
- Uploads and vector_store are persisted using Docker volumes.

## Environment Setup

1. Copy .env.example to .env.
2. Fill in real values for Supabase, LLM keys, and Neo4j credentials.
3. If you are using Docker Compose, set NEO4J_URI to bolt://neo4j:7687 in .env.

## Run the Stack

```powershell
# Build and start

docker compose up -d --build

# Watch logs

docker compose logs -f backend

# Stop

docker compose down
```

## Verify

- Backend health: http://localhost:8000/health
- API docs (via Nginx): http://localhost/docs
- Neo4j browser: http://localhost:7474
- Admin dashboard: http://localhost:8000/admin

## Common Changes

- Change worker count: edit Dockerfile CMD workers value
- Change Nginx rules: edit nginx/nginx.conf
- Change exposed ports: edit docker-compose.yml

## Update and Rebuild

Rebuild backend (use cache):

```powershell
docker compose build backend
docker compose up -d backend
```

Rebuild backend (no cache):

```powershell
docker compose build --no-cache backend
docker compose up -d backend
```

Rebuild everything:

```powershell
docker compose build
docker compose up -d
```

Restart without rebuilding:

```powershell
docker compose restart backend
```

Clean build cache if you see snapshot errors:

```powershell
docker builder prune -af
```

## Troubleshooting

- If /health fails, check backend logs: docker compose logs -f backend
- If Neo4j is not reachable, verify NEO4J_URI and NEO4J_PASSWORD in .env
- If ports are in use, change the host port mappings in docker-compose.yml

## Helpful Notes

- When backend runs in Docker, use service name for Neo4j: NEO4J_URI=bolt://neo4j:7687
- When backend runs locally, use host URI: NEO4J_URI=bolt://localhost:7687
- To avoid Hugging Face rate limits, set HF_TOKEN in .env

## CI/CD (GitHub Actions → Heroku Container)

1) Create these GitHub repo secrets:
- HEROKU_API_KEY (from Heroku Account Settings)
- HEROKU_APP_NAME (your Heroku app name)

Path: GitHub repo → Settings → Secrets and variables → Actions → New repository secret

2) Push to main
- The workflow at .github/workflows/heroku-container-deploy.yml builds and deploys automatically

## Useful Links

- Admin UI: http://localhost:8000/admin
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health
- Neo4j Browser: http://localhost:7474
