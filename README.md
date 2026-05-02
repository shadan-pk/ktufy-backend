# KTUfy Backend

AI-powered study assistant backend for KTU students built with FastAPI.

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or 3.11
- pip (Python package manager)
- Git

### Installation

1. **Clone the repository** (or you're already here!)

2. **Create a virtual environment:**
   ```powershell
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   ```powershell
   .\venv\Scripts\activate
   ```

4. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Configure environment variables:**
   - Copy `.env.example` to `.env`
   - Fill in your Supabase credentials and other settings

6. **Run the development server:**
   ```powershell
   python main.py
   ```
   
   Or using uvicorn directly:
   ```powershell
   uvicorn main:app --reload
   ```

7. **Access the API:**
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

## 🐳 Docker (Production-Style)

This repo includes a full Docker Compose stack with the backend, Nginx reverse proxy, Neo4j, and Redis.

### Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine (Linux)

### First-time Setup
1. **Create your environment file:**
   - Copy `.env.example` to `.env`
   - Fill in Supabase, Neo4j, and LLM credentials

2. **Build and start the stack:**
   ```powershell
   docker compose up -d --build
   ```

3. **Verify services:**
   - Backend health: http://localhost:8000/health
   - API docs (via Nginx): http://localhost/docs
   - Neo4j browser: http://localhost:7474

### Stop and Clean Up
```powershell
docker compose down
```

### Logs
```powershell
docker compose logs -f backend
```

## 📁 Project Structure

```
ktufy-backend/
├── app/                    # Main application code
├── services/               # AI/ML services
├── models/                 # Database models
├── schemas/                # API request/response schemas
├── routers/                # API endpoints
├── utils/                  # Helper functions
├── tests/                  # Unit tests
├── vector_store/           # ChromaDB data (gitignored)
├── uploads/                # Temporary file storage (gitignored)
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (gitignored)
└── .env.example            # Environment template
```

## 🔧 Development Phases

This project follows a structured development roadmap:

- **Phase 1**: Environment Setup ✅ **COMPLETE**
- **Phase 2**: Authentication Integration ✅ **COMPLETE**
- **Phase 3**: Database Schema Design (Next)
- **Phase 4**: Basic API Structure
- **Phase 5**: AI/ML Foundation
- **Phase 6**: KG-RAG Implementation
- **Phase 7**: Content Generation
- **Phase 8**: Async Processing with Celery
- **Phase 9**: Progress Tracking & Analytics
- **Phase 10**: Study Packs & Offline Support
- **Phase 11**: Search & Recommendations
- **Phase 12**: Deployment Preparation

See `ktufy_backend_guide.md` for detailed implementation guide.

## 🛠️ Tech Stack

- **Framework**: FastAPI
- **Database**: Supabase (PostgreSQL)
- **Vector DB**: ChromaDB (to be added in Phase 5)
- **Authentication**: Supabase Auth
- **Storage**: Supabase Storage
- **Task Queue**: Celery + Redis (to be added in Phase 8)
- **LLM**: Ollama / OpenAI (to be configured in Phase 6)

## 📝 API Endpoints

### General Endpoints
- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /api/v1/status` - API status

### Authentication Endpoints (Phase 2) ✅
- `GET /api/v1/auth/me` - Get current user profile 🔒
- `GET /api/v1/auth/status` - Check authentication status
- `POST /api/v1/auth/verify-token` - Verify JWT token
- `GET /api/v1/auth/protected-example` - Protected demo 🔒
- `GET /api/v1/auth/public-example` - Public demo

🔒 = Requires Bearer token

### Upcoming Endpoints
- `/api/v1/notes` - Notes management
- `/api/v1/ai/chat` - KG-RAG chatbot
- `/api/v1/ai/generate` - Content generation
- `/api/v1/progress` - Progress tracking
- And more...

## 🧪 Testing

```powershell
pytest tests/
```

## 📚 Documentation

- Full implementation guide: `ktufy_backend_guide.md`
- API documentation: http://localhost:8000/docs (when running)

## 🔐 Security Notes

- Never commit `.env` file
- Keep Supabase keys secure
- Use different keys for development and production
- Enable Row Level Security (RLS) in Supabase

## 📄 License

[Add your license here]

## 👥 Contributors

[Add contributors here]
