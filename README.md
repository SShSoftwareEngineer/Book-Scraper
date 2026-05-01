# Book Scraper (Async Web Scraping Pipeline)

## Overview
Distributed data extraction system demonstrating ETL principles, async 
processing, and task queue architecture.

## Architecture
[Scrapers (async)] → [Queue] → [Parsers (threads/processes)] → [Queue] → [DB Writer]

## Key Features
- Async HTTP requests (Playwright / aiohttp)
- Task distribution via Celery / queue.Queue
- Multi-threading / multiprocessing for parsing
- Producer-Consumer pattern
- Fault tolerance and retry logic
- PostgreSQL storage

## Technologies
Python, Playwright, aiohttp, Celery, queue.Queue, threading, multiprocessing, BeautifulSoup, 
SQLAlchemy, PostgreSQL

## Why This Matters for Data Engineering
- ETL pipeline design
- Distributed processing
- Task queue management
- Data validation and quality
- Performance optimization

## License

MIT