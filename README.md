# 📚 Book Scraper — Distributed Web Scraping Pipeline

Professional-grade data extraction system demonstrating ETL principles, async processing, and distributed task queue architecture using Celery + Redis.

[![BookScraper CI/CD Pipeline](https://github.com/SShSoftwareEngineer/BookScraper/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/SShSoftwareEngineer/BookScraper/actions)

## 🏗️ Architecture

```
┌─────────────────────┐
│  Main Scraper       │
│  (URL extraction)   │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────┐
    │  Redis Queue │  (Task broker)
    └──────┬───────┘
           │
    ┌──────▼────────────────────┐
    │  Celery Workers × N       │
    │  (async Playwright)       │
    │  (parse books in parallel)│
    └──────┬────────────────────┘
           │
           ▼
    ┌──────────────┐
    │  Redis Cache │  (intermediate storage)
    └──────┬───────┘
           │
           ▼
    ┌──────────────────────┐
    │  Celery Beat         │  (periodic tasks)
    │  (collect_and_save)  │
    └──────┬───────────────┘
           │
           ▼
    ┌──────────────────┐
    │  PostgreSQL DB   │  (final storage)
    └──────────────────┘
```

## ✨ Key Features

- **Async Scraping** — Playwright + asyncio for parallel URL extraction
- **Distributed Tasks** — Celery workers process parsing jobs in parallel
- **Fault Tolerance** — Automatic retry logic, soft/hard time limits
- **Real-time Monitoring** — Flower UI for task tracking and worker status
- **Production-Ready** — Docker multi-stage builds, health checks, logging
- **Windows Compatible** — ProactorEventLoopPolicy for async subprocess handling

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Scraping** | Playwright 1.59+ | Browser automation |
| **Async** | asyncio, aiohttp | Non-blocking I/O |
| **Task Queue** | Celery 5.4+ | Distributed task processing |
| **Message Broker** | Redis 8.0+ | Task queue storage |
| **Database** | PostgreSQL 17 | Persistent data storage |
| **Monitoring** | Flower 2.0+ | Web UI for task tracking |
| **Containerization** | Docker, docker-compose | Reproducible environments |
| **Config** | Pydantic v2 | Type-safe settings |

## 🚀 Quick Start

### Local Development (Poetry)

```bash
# Install dependencies
poetry install

# Copy environment file
cp .env.example .env

# Start Redis in Docker
docker run -d -p 6379:6379 --name redis-book-scraper redis:8-alpine

# Terminal 1: Celery Worker
poetry run celery -A celery_app worker --loglevel=INFO --pool=threads

# Terminal 2: Celery Beat (optional)
poetry run celery -A celery_app beat --loglevel=INFO

# Terminal 3: Flower UI (optional)
poetry run flower -A celery_app --port=5555

# Terminal 4: Run scraper
poetry run python book_scraper.py
```

### Docker Compose (Full Stack)

```bash
# Start all services
docker compose up -d

# Check services
docker compose ps

# View Flower UI
open http://localhost:5555

# Stop everything
docker compose down
```

## 📊 How It Works

1. **URL Extraction Phase**
   - `book_scraper.py` extracts book URLs from website
   - Uses async Playwright for fast parallel scraping
   
2. **Task Distribution Phase**
   - Each URL becomes a Celery task
   - Tasks pushed to Redis queue
   - Workers pick up jobs (concurrency=3 by default)

3. **Parsing Phase**
   - 3 Celery worker threads process tasks in parallel
   - Each thread runs async Playwright in isolated event loop
   - Results cached in Redis
   
4. **Database Write Phase**
   - Periodic `collect_and_save` task batches cached results
   - Writes to PostgreSQL with conflict handling
   - Cleanup from Redis cache

## 🔍 Monitoring

### Flower Web UI
```
http://localhost:5555
```
- Real-time task status
- Worker availability
- Task history and statistics
- Rate limiting controls

### PostgreSQL
```bash
# Connect to database
docker exec postgres-book-scraper psql -U postgres -d book_scraper

# Count saved books
SELECT COUNT(*) FROM books;
```

## 🐳 Docker Multi-Stage Optimization

```dockerfile
Stage 1: Builder
         Creates .venv (150MB)
Stage 2: Base Runtime
         Adds app code (250MB)
Stage 3: Heavy
         Adds Playwright (2GB)
```

- **Celery Beat/Flower** use Stage 2 (250MB each)
- **Celery Worker/Scraper** use Stage 3 (2GB, includes Chromium)

## 🔧 Key Design Decisions

### Windows Compatibility
- `--pool=threads` instead of prefork (Windows doesn't support fork())
- `ProactorEventLoopPolicy` for async subprocess handling
- Dockerfile tested on Windows 10/11 with WSL2

### Async + Threads + GIL
- Threads don't block each other on I/O (await releases GIL)
- 3 threads × async Playwright = real parallelism for network operations
- CPU parsing briefly holds GIL, but negligible overhead

### Fault Tolerance
- `task_acks_late=True` — requeue tasks if worker dies
- `task_time_limit=600s` — kill hung tasks after 10 minutes
- `worker_max_tasks_per_child=100` — restart worker to clean memory

## 📝 Project Structure

```
book-scraper/
├── book_scraper.py          # Main entry point
├── run.py                   # Local launcher
├── celery_app.py            # Celery configuration
├── tasks.py                 # Celery task definitions
├── parsers.py               # Book parsing logic (async)
├── config.py                # Pydantic settings
├── pyproject.toml           # Poetry dependencies
├── Dockerfile               # Multi-stage build
├── docker-compose.yml       # Local deployment
├── .env.example             # Environment template
└── logs/                    # Application logs
```

## 📄 License

MIT License — See LICENSE file

---

**Built for portfolio demonstration of distributed systems, ETL pipelines, and async Python.**
