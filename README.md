# PyFinBot

[![Build Status](https://github.com/GreenMachine582/PyFinBot/actions/workflows/general_tests.yml/badge.svg?branch=main)](https://github.com/GreenMachine582/PyFinBot/actions/workflows/general_tests.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLModel](https://img.shields.io/badge/SQLModel-SQLAlchemy%202.0-red.svg)](https://sqlmodel.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![GitHub release](https://img.shields.io/github/v/release/GreenMachine582/PyFinBot?include_prereleases)

## Table of Contents
- [Introduction](#introduction)
- [Key Features](#-key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Overview](#api-overview)
- [Testing](#testing)
- [Roadmap](#-roadmap)
- [License](#license)
- [Citation](#citation)

---

## Introduction
PyFinBot is a lightweight, extensible financial tracking tool built in Python, designed to help users manage and
analyze their stock trading activity. By leveraging relational database design and SQL-based reporting, PyFinBot
offers precise insights into holdings, transaction history, and capital gains or losses per financial year. Ideal for
personal investors or hobbyist traders, it serves as a transparent and customizable alternative to spreadsheet-based
tracking.

## 🚀 Key Features
* 📊 Transaction Recording: Track Buy/Sell orders with support for fees, prices, values, and financial year grouping.
* 📥 CSV/Excel Import: Bulk-import transactions from a spreadsheet, with per-row validation and error reporting.
* 📆 Holdings Snapshot: Query real-time or historical stock units held as of any given date.
* 💰 Capital Gain/Loss Calculation: Determine net gains/losses per stock by financial year using average cost basis.
* 🔗 Relational Database Design: Clean, normalized schema to ensure data integrity and efficient queries.
* 🔐 Multi-user Support: JWT-authenticated accounts — each user only sees their own transactions and reports.
* 📦 Modular Architecture: Built to be extended with additional features like tax reports, visualizations, or API integration.

## Tech Stack
* **API**: [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
* **ORM / Models**: [SQLModel](https://sqlmodel.tiangolo.com/) on top of SQLAlchemy 2.0 (async)
* **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
* **Database**: PostgreSQL (`asyncpg` / `psycopg2`) in production, SQLite (`aiosqlite`) for tests
* **Import/Reporting**: pandas, openpyxl
* **Testing**: pytest, pytest-asyncio, httpx

## Project Structure
```
src/pyfinbot/
├── api/       # FastAPI routers — users, stocks, transactions, import, reports (auto-registered under /api)
├── core/      # Settings, auth dependencies, sorting/filtering helpers, market sync
├── db/        # Async SQLAlchemy engine/session setup
├── models/    # SQLModel ORM models (User, Stock, Transaction)
├── schemas/   # Pydantic request/response schemas
├── alembic/   # Database migrations
└── pyfinbot.py  # FastAPI app factory / entrypoint
```

## Getting Started

### Prerequisites
* Python 3.12+
* A PostgreSQL database (or SQLite for local experimentation)

### Installation
```bash
git clone https://github.com/GreenMachine582/PyFinBot.git
cd PyFinBot
pip install -r requirements.txt
```

### Configuration
Create a `.env` file in the project root with your database connection strings:
```
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/pyfinbot
ASYNC_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/pyfinbot
SECRET_KEY=<a long random string>

# Optional — only needed for POST /api/emails/sync-commsec
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=<a Gmail App Password, not your regular password>
```
`SECRET_KEY` signs JWT access tokens. If unset, a random key is generated on every process start (fine for local dev, but every restart invalidates all issued tokens) — set it explicitly for any deployment that needs to survive a restart.

`GMAIL_ADDRESS`/`GMAIL_APP_PASSWORD` are only required to use `POST /api/emails/sync-commsec`, which reads Commsec trade confirmation emails via IMAP. An [App Password](https://myaccount.google.com/apppasswords) grants full mailbox read access (not scoped to Commsec mail), so a dedicated Gmail account or label is recommended over your primary inbox.

### Database Migrations
Apply the schema to your database:
```bash
alembic upgrade head
```

### Running the App
```bash
uvicorn src.pyfinbot.pyfinbot:app --reload
```
Or with Docker Compose:
```bash
docker compose up
```
Once running, interactive API docs are available at `http://localhost:8000/docs` (or port `8001` under Docker Compose).

## API Overview
All routes are mounted under `/api`. See `/docs` for full request/response schemas. Every route except `POST /api/users/` (registration) and `POST /api/auth/login` requires a `Bearer` token — register a user, log in to get a token, then pass `Authorization: Bearer <token>` on subsequent requests.

| Router | Prefix | Purpose |
|---|---|---|
| Auth | `/api/auth` | `POST /login` — exchange a user id + password for a JWT access token |
| Users | `/api/users` | Create (register) and manage users |
| Stocks | `/api/stocks` | CRUD for tracked stocks, plus market sync |
| Transactions | `/api/transactions` | CRUD for Buy/Sell transactions |
| Import | `/api/transactions/import` | Bulk-import transactions from CSV/Excel |
| Emails | `/api/emails` | Sync Commsec bought/sold confirmation emails into transactions |
| Dividends | `/api/dividends` | Sync per-stock dividend history (yfinance) |
| Reports | `/api/reports` | Holdings, FY capital-gains, and dividend-income reports |

## Testing
PyFinBot includes a pytest suite covering all routers, models/schemas, and core utilities.

```bash
pytest
```

## 🎯 Roadmap
1. ✅ MVP – Schema design, transaction insertion, and SQL-based queries.
2. ✅ Import System – CSV or Excel import of stock transactions.
3. ✅ Reporting Module – FY-based reports for holdings and capital gains.
4. ✅ Commsec Email Ingestion – Parse bought/sold confirmation emails (Gmail IMAP) into transactions.
5. ✅ Dividend Tracking – Pull per-stock dividend history (yfinance) and report income by FY.
6. 🧮 FIFO Method Support – Accurate gain/loss computation based on FIFO accounting.
7. 🌐 CLI Interface – Interact via command line with exportable summaries.
8. 🖥️ Web Dashboard (optional) – View and interact with data through a simple front end.

Day-to-day and in-progress work is tracked in [`todo.md`](todo.md), which serves as the project's living backlog across sessions.

## License
PyFinBot is licensed under the MIT License, see [LICENSE](LICENSE) for more information.

## Citation
If you use this software, please cite it using the metadata in [`CITATION.cff`](CITATION.cff).
