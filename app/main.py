from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import os
import time
import uuid

from app.database import engine
from app.models import Base
from app import auth, payments
from app.ml.analyzer import router as ml_router  # CORRECTO: ruta absoluta desde app

APP_NAME = "DataSift API"
APP_VERSION = "2.1.0"
APP_DESCRIPTION = "Enterprise-grade data intelligence platform with automated ML analysis"

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("AUTO_CREATE_TABLES", "true") == "true":
        Base.metadata.create_all(bind=engine)
    yield

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
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"]
)

templates = Jinja2Templates(directory="app/templates")

# Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(ml_router, prefix="/api/v1", tags=["Analysis"])

# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "paypal_client_id": os.getenv("PAYPAL_CLIENT_ID", "")}
    )

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "service": APP_NAME, "version": APP_VERSION, "timestamp": int(time.time())}

@app.get("/api/v1/status", tags=["System"])
async def api_status():
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "operational",
        "features": {"authentication": True, "payments": True, "ml_analysis": True, "webhooks": True}
    }

@app.get("/dashboard", tags=["User"])
async def dashboard(user=Depends(auth.get_current_user)):
    usage_percentage = round((user.monthly_requests / user.request_limit) * 100, 2) if user.request_limit > 0 else 0
    return {
        "user": {"id": str(user.id), "email": user.email, "plan": user.plan_id, "status": user.subscription_status},
        "usage": {"requests_used": user.monthly_requests, "request_limit": user.request_limit, "usage_percentage": usage_percentage},
        "api": {"key": user.api_key, "endpoint": "/api/v1/analyze"}
    }

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": True, "code": exc.status_code, "message": exc.detail, "timestamp": int(time.time())})

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": True, "code": 500, "message": "Internal server error", "timestamp": int(time.time())})
