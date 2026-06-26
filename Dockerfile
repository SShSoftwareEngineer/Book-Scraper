# Multi-stage Dockerfile for Book Scraper
# Stage 1: Builder
FROM python:3.14-slim AS builder

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Create virtual environment and install dependencies
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-interaction --no-ansi --no-root

# Force reinstall redis to ensure compatibility with the latest version
RUN poetry run pip install --force-reinstall redis

# Stage 2: Runtime
FROM python:3.14-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create logs directory
RUN mkdir -p logs

# Install Chromium and all system dependencies automatically
RUN apt-get update && \
    playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/* \

# Expose ports
EXPOSE 5555

# Default command: run the launcher
CMD ["python", "book_scraper.py"]

# Available commands:
# docker run ... python run.py                    # Run full system
# docker run ... celery -A celery_app worker      # Run only worker
# docker run ... celery -A celery_app beat        # Run only beat
# docker run ... celery -A celery_app flower      # Run only flower
# docker run ... python book_scraper.py           # Run scraper only
