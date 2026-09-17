# Multi-stage Dockerfile for Book Scraper

# ==========================================
# Stage 1: Builder
# ==========================================
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

# ==========================================
# Stage 2: Base Runtime (for Beat and Flower)
# ==========================================
FROM python:3.14-slim AS runtime-base

WORKDIR /app

# Create non-root user first
RUN groupadd -r appuser && useradd -m -r -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code from builder
COPY . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create required directories and fix permissions
RUN mkdir -p /app/logs /tmp && \
    chown -R appuser:appuser /app /tmp && \
    chmod 777 /tmp /app/logs

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 5555

# ==========================================
# Stage 3: Heavy Runtime (for Worker and Scraper)
# ==========================================
FROM runtime-base AS runtime-heavy

# Temporarily switch back to root for system package installation
USER root

# Configure Playwright to store browsers in a shared, accessible directory
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install Chromium and system dependencies
RUN apt-get update && \
    playwright install-deps chromium && \
    rm -rf /var/lib/apt/lists/* && \
    playwright install chromium && \
    mkdir -p /ms-playwright && \
    chown -R appuser:appuser /ms-playwright

# Switch back to appuser
USER appuser

# Default command: run the launcher
CMD ["python", "book_scraper.py"]


# Available commands:
# docker run ... python run.py                    # Run full system
# docker run ... celery -A celery_app worker      # Run only worker
# docker run ... celery -A celery_app beat        # Run only beat
# docker run ... celery -A celery_app flower      # Run only flower
# docker run ... python book_scraper.py           # Run scraper only
