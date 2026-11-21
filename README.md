# Custom API Gateway with Intelligent Rate Limiting

A high-performance, asynchronous microservices API Gateway built with **FastAPI**, **Redis (Lua Token Bucket)**, **MongoDB**, and **Docker**.

---

## 🏗️ Architecture

```
Client (Web / Mobile / Locust)
              │
              ▼ :5050
     ┌──────────────────┐
     │   API GATEWAY    │ ◄─── Atomic Token Bucket (Redis Lua :6379)
     └─────────┬────────┘
               │ (Internal Docker Network)
  ┌────────────┼────────────┬─────────────┐
  ▼            ▼            ▼             ▼
┌──────────┐ ┌──────────┐ ┌───────────┐ ┌───────────┐
│  Auth    │ │  User    │ │  Product  │ │   Order   │
│ Service  │ │ Service  │ │  Service  │ │  Service  │
│  :5054   │ │  :5051   │ │   :5052   │ │   :5053   │
└────┬─────┘ └────┬─────┘ └─────┬─────┘ └─────┬─────┘
     │            │             │             │
     └────────────┴──────┬──────┴─────────────┘
                         ▼
               ┌──────────────────┐
               │     MONGODB      │
               │    (:27017)      │
               │  - auth_db       │
               │  - user_db       │
               │  - product_db    │
               │  - order_db      │
               └──────────────────┘
```

---

## ✨ Features

- **Asynchronous Reverse Proxy**: Built using FastAPI and `httpx.AsyncClient` for high-throughput, non-blocking proxying.
- **Dedicated Authentication Microservice**:
  - Secure password hashing using **Bcrypt** with dynamic salts.
  - Role-based **JWT tokens** (`free` and `premium` tiers).
- **Atomic Token Bucket Rate Limiting**:
  - Implemented via a **Redis Lua script** executed in-memory.
  - Eliminates race conditions under high concurrency.
  - Tier-aware quotas: Free tier (5 req/60s), Premium tier (20 req/60s).
- **Database-per-Service Pattern**:
  - Independent MongoDB databases (`auth_db`, `user_db`, `product_db`, `order_db`) with auto-seeding on startup.
- **Automated Testing & Load Benchmarking**:
  - Comprehensive **Pytest** integration test suite (`tests/test_integration.py`).
  - **Locust** load testing suite (`locustfile.py`) validating low latency under concurrent load.
- **Security & Observability**:
  - Strict security headers (`X-Frame-Options`, `X-Content-Type-Options`, `HSTS`).
  - Request latency tracking, slow-request detection, and structured logging.
  - Interactive **Swagger UI / OpenAPI documentation** at `http://localhost:5050/docs`.

---

## 🛠️ Tech Stack

- **Gateway & Services**: Python 3.11, FastAPI, Uvicorn, Motor (Async MongoDB), PyJWT, Bcrypt, HTTPX
- **Caching & Rate Limiting**: Redis, Lua
- **Databases**: MongoDB
- **Containerization**: Docker, Docker Compose
- **Testing**: Pytest, Locust

---

## 🚀 Getting Started

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

### 1. Run the Entire Stack
```bash
docker compose up --build -d
```
All 7 services will boot up in detached mode.

### 2. Verify Services
Check running containers:
```bash
docker compose ps
```

Health check:
```bash
curl http://127.0.0.1:5050/
```
Expected output:
```json
{"message": "Custom API Gateway Running"}
```

---

## 📖 API Documentation & Endpoints

| Endpoint | Target Service | Access | Description |
|---|---|---|---|
| `GET /` | Gateway | Public | Gateway health check |
| `POST /auth/register` | Auth Service (:5054) | Public | Register new user (hashes password via Bcrypt) |
| `POST /auth/login` | Auth Service (:5054) | Public | Login & receive signed JWT Bearer token |
| `GET /api/users` | User Service (:5051) | Public | Retrieve user directory |
| `GET /api/products` | Product Service (:5052) | Public | Retrieve product catalog |
| `GET /api/orders` | Order Service (:5053) | **Protected** | Requires JWT Bearer token & rate limited |

Interactive documentation is available at:
- **API Gateway Swagger**: [http://localhost:5050/docs](http://localhost:5050/docs)
- **Auth Service Swagger**: [http://localhost:5054/docs](http://localhost:5054/docs)

---

## 🧪 Running Tests

### Pytest Integration Suite
Ensure containers are running, then run:
```bash
pytest tests/test_integration.py -v
```

### Locust Load Testing
Start the Locust web UI:
```bash
locust -f locustfile.py
```
Open [http://localhost:8089](http://localhost:8089) in your browser to simulate concurrent users.
