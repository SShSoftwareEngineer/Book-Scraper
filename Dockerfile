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
    poetry install --no-interaction --no-ansi --no-root && \
    rm -rf /root/.cache/pip

# Force reinstall redis to ensure compatibility with the latest version
RUN poetry run pip install --force-reinstall redis

# Stage 2: Base Runtime (for Beat and Flower)
#FROM python:3.14-slim
FROM python:3.14-slim AS runtime-base

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

# Expose ports
EXPOSE 5555

# Stage 3: Heavy Runtime (only for Worker and Scraper)
FROM runtime-base AS runtime-heavy

# Install Chromium and all system dependencies automatically
RUN apt-get update && \
    playwright install-deps chromium && \
    rm -rf /var/lib/apt/lists/* && \
    playwright install chromium

# Creating a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Changing Permissions
WORKDIR /app
RUN chown -R appuser:appuser /app
USER appuser  # run as appuser, not root

# Make / read-only where possible
RUN mkdir -p /tmp /app/logs && chmod 777 /tmp /app/logs

# Default command: run the launcher
CMD ["python", "book_scraper.py"]


# Available commands:
# docker run ... python run.py                    # Run full system
# docker run ... celery -A celery_app worker      # Run only worker
# docker run ... celery -A celery_app beat        # Run only beat
# docker run ... celery -A celery_app flower      # Run only flower
# docker run ... python book_scraper.py           # Run scraper only