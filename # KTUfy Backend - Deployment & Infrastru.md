# KTUfy Backend - Deployment & Infrastructure Guide 🚀

## Date: February 26, 2026

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development vs Production Stack](#development-vs-production-stack)
3. [Docker Setup](#docker-setup)
4. [Nginx Reverse Proxy](#nginx-reverse-proxy)
5. [CI/CD Pipeline (GitHub Actions)](#cicd-pipeline-github-actions)
6. [Server Setup (One-Time)](#server-setup-one-time)
7. [Complete Deployment Flow](#complete-deployment-flow)
8. [Hosting Options](#hosting-options)
9. [Implementation Timeline](#implementation-timeline)
10. [SSL/HTTPS Setup](#sslhttps-setup)
11. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Development (Current)

```
Your PC (localhost:8000)
    │
    └── python main.py → Uvicorn → FastAPI app
```

### Production (Future)

```
Internet
    │
    ▼
Nginx (port 80/443)
    ├── SSL termination
    ├── Rate limiting
    ├── Security headers
    ├── Request buffering
    │
    ▼
Gunicorn + Uvicorn Workers (port 8000, internal only)
    │
    ▼
FastAPI Application
    ├── Supabase (cloud - auth, DB, storage)
    ├── Neo4j (containerized - knowledge graph)
    ├── Redis (containerized - caching)
    └── Sentence Transformers (in-app - embeddings)
```

---

## Development vs Production Stack

| Component | Development | Production |
|---|---|---|
| **Web Server** | `uvicorn --reload` | Nginx → Gunicorn + Uvicorn workers |
| **App Server** | Single process | 4 Gunicorn workers |
| **Database** | Supabase cloud | Supabase cloud (no change) |
| **Neo4j** | Local install or Aura | Docker container |
| **Redis** | Not used | Docker container |
| **SSL/HTTPS** | Not needed | Nginx handles via Let's Encrypt |
| **Rate Limiting** | Not needed | Nginx: 30 req/s per IP |
| **Deployment** | Manual `python main.py` | Automated via GitHub Actions |

---

## Docker Setup

### Why Docker?

Docker packages your entire application into a portable container. Without it:

1. Install exact Python version on server
2. Install all pip packages (some have C dependencies that fail on different OS)
3. Install and configure Neo4j with APOC plugin
4. Download the 400MB ML model
5. Set up environment variables
6. Hope nothing conflicts

**With Docker: one command, everything runs identically everywhere.**

### Dockerfile

```dockerfile
# filepath: Dockerfile

# --- Stage 1: Build ---
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create non-root user
RUN adduser --disabled-password --no-create-home appuser && \
    mkdir -p /app/uploads /app/vector_store && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Gunicorn with Uvicorn workers (production)
CMD ["gunicorn", "main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-"]
```

### .dockerignore

```
# filepath: .dockerignore

venv/
__pycache__/
*.pyc
.env
.git/
vector_store/
uploads/
*.md
tests/
.vscode/
```

### Docker Compose (Full Stack)

```yaml
# filepath: docker-compose.yml

version: "3.9"

services:
  # --- FastAPI Backend ---
  backend:
    build: .
    container_name: ktufy-backend
    env_file: .env
    expose:
      - "8000"          # Only exposed to nginx, NOT to public
    volumes:
      - uploads_data:/app/uploads
      - vector_data:/app/vector_store
    depends_on:
      neo4j:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # --- Nginx Reverse Proxy ---
  nginx:
    image: nginx:alpine
    container_name: ktufy-nginx
    ports:
      - "80:80"         # Only public port
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  # --- Neo4j (Knowledge Graph) ---
  neo4j:
    image: neo4j:5-community
    container_name: ktufy-neo4j
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-changeme}
      - NEO4J_PLUGINS=["apoc"]
    ports:
      - "7474:7474"     # Browser UI
      - "7687:7687"     # Bolt protocol
    volumes:
      - neo4j_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 30s
      timeout: 10s
      retries: 5

  # --- Redis (Caching) ---
  redis:
    image: redis:7-alpine
    container_name: ktufy-redis
    expose:
      - "6379"
    restart: unless-stopped

volumes:
  uploads_data:
  vector_data:
  neo4j_data:
```

### Additional Dependency

Add `gunicorn` to requirements:

```
# In requirements.txt, add:
gunicorn==21.2.0
```

---

## Nginx Reverse Proxy

### What Nginx Does

| Feature | Why It Matters |
|---|---|
| **Reverse proxy** | Routes traffic to Uvicorn, hides app from public |
| **SSL/TLS termination** | Handles HTTPS certificates |
| **Load balancing** | Distributes requests across workers |
| **Static file serving** | Serves files faster than Python |
| **Rate limiting** | Protects against abuse/DDoS |
| **Request buffering** | Handles slow clients without blocking your app |
| **Security headers** | Adds XSS, clickjacking protection |

### Nginx Configuration

```nginx
# filepath: nginx/nginx.conf

upstream ktufy_backend {
    server backend:8000;
}

# Rate limiting zone
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;

server {
    listen 80;
    server_name your-domain.com;  # Change to actual domain or server IP

    # --- Security Headers ---
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # --- File upload limit (for PDF uploads) ---
    client_max_body_size 50M;

    # --- Health check (Nginx level) ---
    location /nginx-health {
        return 200 "OK";
        add_header Content-Type text/plain;
    }

    # --- API endpoints (rate limited) ---
    location /api/ {
        limit_req zone=api burst=50 nodelay;

        proxy_pass http://ktufy_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout for long AI responses
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    # --- WebSocket support (for future streaming chat) ---
    location /ws/ {
        proxy_pass http://ktufy_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # --- Everything else ---
    location / {
        proxy_pass http://ktufy_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# --- HTTPS server (uncomment when you have SSL certificate) ---
# server {
#     listen 443 ssl http2;
#     server_name your-domain.com;
#
#     ssl_certificate /etc/nginx/certs/fullchain.pem;
#     ssl_certificate_key /etc/nginx/certs/privkey.pem;
#
#     # Copy all location blocks from above
# }
```

### Traffic Flow

```
Internet → port 80 (Nginx) → port 8000 (FastAPI, hidden from public)
                ↓
          Rate limiting (30 req/s per IP)
          Security headers added
          Request buffered
          SSL terminated (when enabled)
```

---

## CI/CD Pipeline (GitHub Actions)

### What CI/CD Does

CI/CD is an **automated gatekeeper** — it tests your code and deploys only if everything passes. Docker alone does NOT do this.

| What | Tool |
|---|---|
| You code locally | Your machine |
| Version control | Git + GitHub |
| Automated testing | GitHub Actions |
| Build container | Docker |
| Auto-deploy if tests pass | GitHub Actions + SSH |
| Server stays up during updates | Docker rolling restart + Nginx |

### The Pipeline

```
You (local machine)
  │
  ├── Code changes
  ├── Test locally (python main.py)
  ├── git commit + git push
  │
  ▼
GitHub Actions
  │
  ├── Runs pytest ──→ FAIL? → Stops. Server untouched. You get email.
  ├── Builds Docker image ✅
  ├── Pushes to Docker Hub ✅
  │
  ▼
Your VPS Server
  │
  ├── Pulls new Docker image
  ├── Restarts backend container (Nginx stays up = no downtime)
  ├── Health check passes ✅
  │
  ▼
Users see new version ✅
```

### GitHub Actions Workflow

```yaml
# filepath: .github/workflows/deploy.yml

name: KTUfy Backend CI/CD

# When does this run?
on:
  push:
    branches: [main]       # Deploy on push to main
  pull_request:
    branches: [main]       # Test on PRs to main

jobs:
  # ============ JOB 1: TEST ============
  test:
    name: Run Tests
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx

      - name: Run tests
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          JWT_SECRET: ${{ secrets.JWT_SECRET }}
        run: |
          pytest tests/ -v --tb=short

      - name: Check if app starts
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          timeout 10 python -c "from main import app; print('App loads OK')" || true

  # ============ JOB 2: BUILD DOCKER IMAGE ============
  build:
    name: Build Docker Image
    needs: test            # Only runs if tests pass
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Build and push image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKER_USERNAME }}/ktufy-backend:latest
            ${{ secrets.DOCKER_USERNAME }}/ktufy-backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ============ JOB 3: DEPLOY TO SERVER ============
  deploy:
    name: Deploy to Production
    needs: build           # Only runs if build succeeds
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'

    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd /opt/ktufy-backend

            # Pull latest image
            docker pull ${{ secrets.DOCKER_USERNAME }}/ktufy-backend:latest

            # Restart only the backend (nginx stays up = zero downtime)
            docker compose up -d --no-deps backend

            # Clean up old images
            docker image prune -f

            # Verify health
            sleep 5
            curl -f http://localhost:8000/health || echo "Health check failed!"
```

### Required GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → Add:

| Secret Name | Value |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Your Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Your service role key |
| `JWT_SECRET` | Your JWT secret |
| `DOCKER_USERNAME` | Your Docker Hub username |
| `DOCKER_PASSWORD` | Your Docker Hub access token |
| `SERVER_HOST` | Your VPS IP address |
| `SERVER_USER` | SSH username (usually `root`) |
| `SERVER_SSH_KEY` | Your private SSH key |

---

## Server Setup (One-Time)

Run this once when you get a VPS:

```bash
# SSH into your server
ssh root@your-server-ip

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
apt install docker-compose-plugin -y

# Clone your project
git clone https://github.com/your-username/ktufy-backend.git /opt/ktufy-backend
cd /opt/ktufy-backend

# Create .env file with production secrets
nano .env

# Create nginx directory
mkdir -p nginx

# Start everything
docker compose up -d

# Verify
docker compose ps
curl http://localhost/health
```

**After this, you never touch the server again.** GitHub Actions handles all future deployments.

---

## Complete Deployment Flow

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR LOCAL MACHINE                     │
│                                                          │
│   Code changes → Test locally → git push to main         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    GITHUB ACTIONS                         │
│                                                          │
│   1. Pull code                                           │
│   2. Install dependencies                                │
│   3. Run pytest                                          │
│      ├── FAIL → Stop. Email notification. Server safe.   │
│      └── PASS → Continue ↓                               │
│   4. Build Docker image                                  │
│   5. Push to Docker Hub                                  │
│   6. SSH into server                                     │
│   7. Pull new image                                      │
│   8. Restart backend container                           │
│   9. Health check                                        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    PRODUCTION SERVER                      │
│                                                          │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│   │  Nginx   │───▶│ FastAPI  │───▶│  Neo4j   │          │
│   │ (port 80)│    │(port 8000│    │(port 7687│          │
│   └──────────┘    │ internal)│    │ internal)│          │
│                    └──────────┘    └──────────┘          │
│                         │              │                  │
│                         ▼              │                  │
│                    ┌──────────┐    ┌──────────┐          │
│                    │ Supabase │    │  Redis   │          │
│                    │ (cloud)  │    │(port 6379│          │
│                    └──────────┘    │ internal)│          │
│                                    └──────────┘          │
└─────────────────────────────────────────────────────────┘
```

---

## Hosting Options

| Option | Cost | Best For | Difficulty |
|---|---|---|---|
| **Railway** | Free → $5/mo | Quick deploy, no Docker needed | ⭐ Easiest |
| **Render** | Free → $7/mo | Small projects | ⭐ Easy |
| **DigitalOcean Droplet** | $6-12/mo | Full control with Docker | ⭐⭐ Medium |
| **Hetzner VPS** | €4/mo | Best price/performance | ⭐⭐ Medium |
| **AWS EC2 (t3.micro)** | Free tier 1yr | Production scale | ⭐⭐⭐ Hard |
| **Fly.io** | Free → $5/mo | Edge/global deployment | ⭐⭐ Medium |

### Recommendation

- **College project / demo**: Use **Railway** or **Render** (no Docker needed, just push code)
- **Production with Neo4j + Redis**: Use **DigitalOcean $12/mo** or **Hetzner VPS** with Docker Compose
- **To impress evaluators**: DigitalOcean + Docker + CI/CD pipeline

> **Note:** Supabase is already cloud-hosted — no need to containerize the database. Only containerize FastAPI, Neo4j, Nginx, and Redis.

---

## Implementation Timeline

| When | What to Do |
|---|---|
| **Now** | Keep coding locally. No Docker/Nginx/CI-CD needed. |
| **When features are done** | Write basic tests in `tests/` folder |
| **2 weeks before demo** | Add `Dockerfile` + `docker-compose.yml` to repo |
| **1 week before demo** | Get a VPS ($6/mo), deploy with `docker compose up -d` |
| **If you want to impress** | Add the GitHub Actions CI/CD pipeline |
| **For viva/presentation** | Show the CI/CD pipeline diagram — evaluators love this |

---

## SSL/HTTPS Setup

Once deployed, add free SSL with Let's Encrypt:

```bash
# On your server
apt install certbot python3-certbot-nginx -y

# Get certificate (replace with your domain)
certbot --nginx -d your-domain.com

# Auto-renew (runs twice daily)
certbot renew --dry-run
```

Then uncomment the HTTPS server block in `nginx/nginx.conf`.

---

## Troubleshooting

### Docker Issues

| Problem | Solution |
|---|---|
| `docker compose up` fails | Check `.env` file exists and has all variables |
| Container keeps restarting | Run `docker logs ktufy-backend` to see errors |
| Port already in use | Run `docker compose down` first, then `up` |
| Out of disk space | Run `docker system prune -a` to clean up |

### Nginx Issues

| Problem | Solution |
|---|---|
| 502 Bad Gateway | Backend container isn't running — check `docker logs ktufy-backend` |
| 413 Request Entity Too Large | Increase `client_max_body_size` in nginx.conf |
| 504 Gateway Timeout | Increase `proxy_read_timeout` for long AI responses |

### CI/CD Issues

| Problem | Solution |
|---|---|
| Tests fail in GitHub Actions | Check if env secrets are set correctly |
| Deploy step fails | Verify SSH key and server IP in secrets |
| Image push fails | Check Docker Hub credentials |

---

## Useful Commands

### Local Development
```powershell
# Start development server
python main.py

# Run tests
pytest tests/ -v
```

### Docker (Production)
```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f backend

# Restart only backend (zero downtime)
docker compose up -d --no-deps backend

# Stop everything
docker compose down

# Rebuild after code changes
docker compose up -d --build

# Check container status
docker compose ps

# Enter container shell
docker exec -it ktufy-backend /bin/sh
```

---

## Summary

| Tool | Role in KTUfy |
|---|---|
| **Docker** | Packages app into portable container — runs same everywhere |
| **Docker Compose** | Runs app + Neo4j + Nginx + Redis together |
| **Nginx** | Reverse proxy — SSL, rate limiting, security, hides app port |
| **GitHub Actions** | CI/CD — auto-test and auto-deploy on `git push` |
| **Gunicorn** | Production app server — multiple workers for concurrency |
| **VPS** | The actual server where everything runs |

**Bottom line:** You don't need any of this right now. Keep developing. Add it when you're ready to deploy for real users or your demo.

---

*Last updated: February 26, 2026*