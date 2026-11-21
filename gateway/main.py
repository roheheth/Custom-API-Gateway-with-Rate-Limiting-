import os
import time
import datetime
from contextlib import asynccontextmanager
import jwt
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from fastapi.openapi.utils import get_openapi
from dotenv import load_dotenv

# Load env variables
load_dotenv()

from logger import logger
from config.redis_config import redis_client, check_redis_connection
from middleware.auth import auth_middleware, JWT_SECRET
from middleware.rate_limiter import rate_limiter
from routes.routes_config import ROUTES_CONFIG

# Lifespan manager for FastAPI (startup and shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connection verification & client init
    await check_redis_connection()
    app.state.http_client = httpx.AsyncClient()
    yield
    # Shutdown: clean connections
    await redis_client.close()
    await app.state.http_client.aclose()

security_scheme = HTTPBearer(auto_error=False)

app = FastAPI(
    title="API Gateway",
    description="Microservices API Gateway with JWT Auth and Rate Limiting",
    version="1.0.0",
    lifespan=lifespan
)

# Custom OpenAPI schema to inject Bearer token security globally
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Inject the Bearer security scheme
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    # Apply security globally to all routes
    for path in schema.get("paths", {}).values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi


# ======================================
# GLOBAL MIDDLEWARES (CORS)
# ======================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================
# REQUEST LOGGER, LATENCY & SECURITY MIDDLEWARE
# ======================================
@app.middleware("http")
async def process_requests(request: Request, call_next):
    # Original URL containing path and query string
    original_url = request.url.path
    if request.url.query:
        original_url += f"?{request.url.query}"

    # Log incoming request
    logger.info(f"{request.method} {original_url}")
    
    start_time = time.time()
    
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Request error: {str(e)}")
        response = JSONResponse(
            status_code=500,
            content={"message": "Internal server error"}
        )

    duration_ms = int((time.time() - start_time) * 1000)

    # Log request stats
    logger.info(
        f"{request.method} {original_url} | Status: {response.status_code} | {duration_ms}ms"
    )

    # Slow Request Detection
    if duration_ms > 1000:
        logger.error(
            f"SLOW REQUEST: {request.method} {original_url} took {duration_ms}ms"
        )

    # Helmet-like Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=15552000; includeSubDomains"
    
    return response

# ======================================
# HEALTH CHECK ROUTE
# ======================================
@app.get("/")
def health_check():
    return {"message": "Custom API Gateway Running"}
# ======================================
# DYNAMIC ROUTE LOADER
# ======================================
def make_proxy_route(service):
    async def handler(request: Request):
        # Protected Routes
        if service["protected"]:
            # Run JWT Auth Middleware
            auth_res = await auth_middleware(request)
            if auth_res is not None:
                return auth_res

            # Run Rate Limiter Middleware
            rate_res = await rate_limiter(request)
            if rate_res is not None:
                return rate_res

        # Resolve Target URL and path stripping
        path = request.url.path
        prefix = service["route"]
        if path.startswith(prefix):
            suffix = path[len(prefix):]
        else:
            suffix = path

        # Ensure correct formatting of relative path suffix
        if not suffix:
            suffix = "/"
        elif not suffix.startswith("/"):
            suffix = "/" + suffix

        target_url = service["target"].rstrip("/") + suffix
        if request.url.query:
            target_url += f"?{request.url.query}"

        # Proxy request properties
        body = await request.body()
        headers = dict(request.headers)
        # Remove host header to allow target service to resolve host independently (changeOrigin)
        headers.pop("host", None)

        try:
            client = request.app.state.http_client
            logger.info(f"Forwarding {request.method} {request.url.path} -> {service['target']}")
            
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                timeout=30.0
            )

            # Exclude backend response headers that should not be forwarded directly
            exclude_headers = ["content-length", "transfer-encoding", "connection", "keep-alive"]
            response_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in exclude_headers
            }

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=response_headers
            )
        except Exception as e:
            logger.error(f"Error proxying request to {service['target']}: {str(e)}")
            return JSONResponse(
                status_code=502,
                content={"message": f"Bad Gateway: {str(e)}"}
            )
            
    return handler

# Register Routes Dynamically
for service in ROUTES_CONFIG:
    handler = make_proxy_route(service)
    methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
    app.api_route(service["route"], methods=methods)(handler)
    app.api_route(service["route"] + "/{path:path}", methods=methods)(handler)
