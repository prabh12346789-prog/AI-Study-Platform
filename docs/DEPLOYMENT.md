# UPSC AI Mentor — Deployment Guide

This guide covers deployment options for the UPSC AI Mentor platform: local Docker Compose, cloud deployments on Render, and manual setup.

## Quick Start: Local Docker Deployment

### Prerequisites
- Docker and Docker Compose installed
- Ollama running locally (or use the Ollama service in docker-compose)
- 2GB+ free disk space for models and databases

### Local Deployment with Docker Compose

```bash
# Clone the repository
git clone https://github.com/prabh12346789-prog/AI-Study-Platform.git
cd AI-Study-Platform

# Create .env in backend directory
cp backend/.env.example backend/.env

# Start all services
docker-compose up -d

# Wait for Ollama to initialize (30-60 seconds)
# Pull required models
docker exec ai-study-backend sh -c 'sleep 30 && ollama pull qwen2.5:3b && ollama pull nomic-embed-text'

# Verify services
docker-compose ps
```

**Access the application:**
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

### Environment Variables for Local Deployment

Edit `backend/.env`:
```env
DATABASE_URL=sqlite:///./data/app.sqlite3
MEMORY_DB_PATH=./data/memory.sqlite3
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:3b
EMBEDDING_PROVIDER=ollama
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
CHROMA_COLLECTION=upsc_mentor
INTERNAL_ADMIN_KEY=local-dev-key-change-in-production
```

---

## Render Cloud Deployment

### Prerequisites
- GitHub account with this repository
- Render.com account (free tier available)
- Database storage (SQLite can be used with limitations; PostgreSQL recommended for production)

### Step 1: Connect Repository to Render

1. Go to [render.com](https://render.com)
2. Sign in with GitHub
3. Create a new "Blueprint" project
4. Select this repository: `prabh12346789-prog/AI-Study-Platform`
5. Render will auto-detect `render.yaml`

### Step 2: Configure Environment Variables

In Render Dashboard, set these environment variables for the **backend service**:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | `sqlite:///./data/app.sqlite3` | SQLite for free tier; use PostgreSQL for production |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama or managed service URL |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Model name |
| `EMBEDDING_PROVIDER` | `ollama` | Embedding provider |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `CHROMA_COLLECTION` | `upsc_mentor` | ChromaDB collection name |
| `INTERNAL_ADMIN_KEY` | `your-secure-key-here` | Generate a strong random key |
| `CORS_ORIGINS` | `https://your-frontend-url.onrender.com` | CORS configuration |

### Step 3: Deploy

1. Click "Deploy Blueprint"
2. Render will:
   - Build and start the backend service
   - Build and start the frontend service
   - Configure CORS between frontend and backend automatically
3. Wait for both services to complete (5-10 minutes)

### Step 4: Initialize Models

After deployment, SSH into the backend service and pull models:

```bash
# Via Render dashboard terminal or CLI
cd /app
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

### Verify Deployment

- **Frontend**: Visit `https://your-frontend-url.onrender.com`
- **Backend API**: Visit `https://your-backend-url.onrender.com/docs`
- **Health Check**: `curl https://your-backend-url.onrender.com/`

---

## Manual Setup (Windows)

### Backend Setup

```powershell
cd backend

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt

# Configure environment
Copy-Item .env.example .env
# Edit .env with your settings

# Start Ollama (in another terminal)
ollama serve

# In a third terminal, start the backend
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend Setup

```powershell
cd upsc-ai-test-frontend-flat

# Install dependencies
npm install

# Configure environment
Copy-Item .env.example .env

# Start development server
npm run dev
```

Open `http://127.0.0.1:5173` in your browser.

---

## Production Checklist

- [ ] Set `INTERNAL_ADMIN_KEY` to a strong, randomly generated key
- [ ] Use PostgreSQL instead of SQLite for production
- [ ] Enable HTTPS/TLS on both frontend and backend
- [ ] Configure CORS to restrict to known frontend origins
- [ ] Set up regular database backups
- [ ] Monitor Ollama memory usage and set resource limits
- [ ] Use environment-specific `.env` files (never commit `.env`)
- [ ] Run test suite before deployment: `python -m pytest -q`
- [ ] Test frontend build: `npm run build`
- [ ] Enable rate limiting on API endpoints
- [ ] Set up logging and monitoring

---

## Troubleshooting

### "Connection refused" between frontend and backend
- Verify `VITE_API_BASE_URL` in frontend `.env` matches backend URL
- Check CORS configuration in `backend/src/main.py`
- Ensure backend service is running and accessible

### "Ollama models not found"
```bash
# Manually pull models
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
ollama list
```

### Database locked error
- SQLite has concurrency limits; use PostgreSQL for production
- Ensure only one instance of the backend is running

### Slow responses on cloud deployment
- Ollama inference can take 10-30s per query on free-tier cloud resources
- Consider upgrading to a paid tier or using a local Ollama service
- Monitor backend logs for timeouts

### Build failures
- Check `requirements.txt` version compatibility
- Run `npm install` separately if frontend build fails
- Verify Python and Node.js versions on deployment platform

---

## Monitoring and Logging

### Local Docker
```bash
# View backend logs
docker-compose logs backend

# View frontend logs
docker-compose logs frontend

# View Ollama logs
docker-compose logs ollama

# Follow logs in real-time
docker-compose logs -f
```

### Render
- Dashboard → Services → Select service → Logs tab
- Real-time logs available; retention depends on tier

---

## Scaling Considerations

- **Ollama inference**: Runs locally; optimize model size or use quantized versions
- **Database**: Scale from SQLite → PostgreSQL as user base grows
- **Concurrency**: Each free-tier Render service handles ~50 concurrent requests
- **Storage**: Monitor `/app/data` directory size; SQLite file growth depends on users and PDFs

---

## Support and Next Steps

For issues, refer to:
- Main README: `../README.md`
- Project State: `../docs/PROJECT_STATE.md`
- Architecture Decisions: `../docs/DECISIONS.md`

To contribute deployment improvements, open an issue or PR on the GitHub repository.
