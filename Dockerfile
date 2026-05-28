# Multi-stage Dockerfile for Book Scraper
# Stage 1: Builder
FROM python:3.14-slim as builder

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Create virtual environment and install dependencies
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-interaction --no-ansi

# Stage 2: Runtime
FROM python:3.14-slim

WORKDIR /app

# Install runtime dependencies (Playwright needs extra packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgconf-2-4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxrandr2 \
    libxinerama1 \
    libxi6 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxext6 \
    libxrender1 \
    libgbm1 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpixman-1-0 \
    libxss1 \
    libasound2 \
    libexpat1 \
    libssl3 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Копируй весь код
COPY . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create logs directory
RUN mkdir -p logs

# Install Playwright browsers
RUN playwright install chromium

# Expose ports
EXPOSE 5555 6379

# Default command: run the launcher
CMD ["python", "run.py"]

#CMD ["python", "book_scraper.py"]

# Available commands:
# docker run ... python run.py                    # Run full system
# docker run ... celery -A celery_app worker      # Run only worker
# docker run ... celery -A celery_app beat        # Run only beat
# docker run ... celery -A celery_app flower      # Run only flower
# docker run ... python book_scraper.py           # Run scraper only
