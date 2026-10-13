import logging
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

# Configure logging with standard format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Enable flexible imports whether running from root or from within backend/
try:
    from backend.chat import router as chat_router, limiter
    from backend.tools import router as tools_router
except ImportError:
    from chat import router as chat_router, limiter
    from tools import router as tools_router

app = FastAPI(
    title="Personal AI - Competitive Programming & DSA Coach",
    description="Backend API with real-time streaming chat powered by Groq & local embeddings.",
    version="0.1.0",
)

# CORS configuration for frontend clients
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://personallai.vercel.app",
]
env_origins = os.getenv("ALLOWED_ORIGINS", "")
if env_origins:
    for origin in env_origins.split(","):
        cleaned = origin.strip().rstrip("/")
        if cleaned and cleaned not in origins:
            origins.append(cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-Id", "X-Rag-Chunks", "X-Rag-Sources"],
)

# Rate limiter state registration
app.state.limiter = limiter

# Rate limit exception handler (returns clear 429 JSON message)
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    client_ip = request.client.host if request.client else "unknown"
    logger.warning("Rate limit exceeded for %s from IP %s: %s", request.url.path, client_ip, exc)
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. You're sending messages too quickly, try again in a minute.",
            "error_type": "RateLimitExceeded",
        },
    )

# Global unhandled exception handler to guarantee clean JSON errors with proper status codes
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception for %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error. Please check server logs.",
            "error_type": exc.__class__.__name__,
        },
    )

# Register route handlers
app.include_router(chat_router)
app.include_router(tools_router)


@app.get("/")
async def root():
    """Health and status endpoint."""
    return {
        "status": "online",
        "service": "Personal AI - DSA Coach API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "chat": "POST /chat",
            "transcribe": "POST /transcribe",
            "conversations": "GET, POST /conversations",
            "conversation_detail": "GET, DELETE /conversations/{conversation_id}",
            "rag_status": "GET /rag/status",
            "rag_query": "GET /rag/query?q={query}&top_k={k}",
            "rag_index": "POST /rag/index",
            "tools": "GET /tools",
            "tools_execute": "POST /tools/execute",
        },
    }


