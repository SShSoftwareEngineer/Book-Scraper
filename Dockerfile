FROM python:3.14-slim

WORKDIR /app

# docker-compose.yml
env_file:
- .env.docker

# Установи зависимости системы
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Установи Poetry
RUN pip install poetry

# Копируй файлы зависимостей
COPY pyproject.toml poetry.lock* ./

# Установи зависимости
RUN poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction

# Копируй весь код
COPY . .

# Создай директорию логов
RUN mkdir -p logs

CMD ["python", "book_scraper.py"]