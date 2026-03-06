"""
DataSift API - Enterprise Data Intelligence Platform
"""
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import os
import time
import secrets

from .database import engine, get_db
from .models import Base
from . import auth, payments
from .ml.analyzer import router as ml_router

# Application metadata
APP_NAME = "DataSift API"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Enterprise-grade data intelligence platform with automated ML analysis"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown


# Initialize FastAPI app
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure for production
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"]
)

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(ml_router, prefix="/api/v1", tags=["Analysis"])


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Request-ID"] = secrets.token_hex(8)
    return response


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request):
    """Serve the main landing page"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "paypal_client_id": os.getenv("PAYPAL_CLIENT_ID", "")
    })


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": APP_NAME,
        "version": APP_VERSION,
        "timestamp": int(time.time())
    }


@app.get("/api/v1/status", tags=["System"])
async def api_status():
    """Detailed API status and capabilities"""
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "operational",
        "features": {
            "authentication": True,
            "payments": True,
            "ml_analysis": True,
            "webhooks": True
        },
        "endpoints": {
            "documentation": "/docs",
            "authentication": "/auth",
            "analysis": "/api/v1/analyze",
            "payments": "/payments"
        }
    }


@app.get("/dashboard", tags=["User"])
async def dashboard(user=Depends(auth.get_current_user)):
    """Get user dashboard data"""
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "plan": user.plan_id,
            "status": user.subscription_status
        },
        "usage": {
            "requests_used": user.monthly_requests,
            "request_limit": user.request_limit,
            "usage_percentage": round((user.monthly_requests / user.request_limit) * 100, 2) if user.request_limit > 0 else 0
        },
        "api": {
            "key": user.api_key,
            "endpoint": "/api/v1/analyze"
        },
        "subscription": {
            "end_date": user.subscription_end_date.isoformat() if user.subscription_end_date else None,
            "days_remaining": (user.subscription_end_date - __import__('datetime').datetime.utcnow()).days if user.subscription_end_date else None
        } if user.subscription_end_date else None
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": exc.status_code,
            "message": exc.detail,
            "timestamp": int(time.time())
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "code": 500,
            "message": "Internal server error",
            "timestamp": int(time.time())
        }
    )
