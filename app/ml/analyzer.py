"""
ML Analysis API - Enterprise-grade data analysis with machine learning
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import pandas as pd
import io
import time
import hashlib

# Corrección de imports según tu estructura original
from app.auth import get_current_user
from app.database import get_db
from app.models import User, AnalysisReport
from app.ml.enhanced_analyzer import EnhancedDataAnalyzer

router = APIRouter()

# -----------------------------
# Pydantic models
# -----------------------------
class AnalysisSummary(BaseModel):
    overall: Dict[str, Any]
    numeric_stats: Optional[Dict[str, Any]] = None
    categorical_stats: Optional[Dict[str, Any]] = None

class Pattern(BaseModel):
    type: str
    description: str
    confidence: float
    details: Optional[Dict[str, Any]] = None

class Recommendation(BaseModel):
    priority: str
    category: str
    message: str
    action: str

class AnalysisResponse(BaseModel):
    id: str
    dataset_name: str
    dataset_hash: str
    summary: AnalysisSummary
    patterns: List[Pattern]
    recommendations: List[Recommendation]
    processing_time_ms: int
    requests_remaining: int
    timestamp: str

class ReportSummary(BaseModel):
    id: str
    dataset_name: str
    created_at: str
    processing_time_ms: int

class UsageStats(BaseModel):
    total_requests: int
    requests_this_month: int
    request_limit: int
    usage_percentage: float
    datasets_analyzed: int

# -----------------------------
# Helpers
# -----------------------------
def generate_dataset_hash(content: bytes) -> str:
    """Generate MD5 hash of dataset content"""
    return hashlib.sha256(content).hexdigest()[:32]

def check_file_size_limit(file_size: int, user: User) -> bool:
    plan_limits = {
        "free": 10 * 1024 * 1024,
        "pro": 100 * 1024 * 1024,
        "enterprise": 500 * 1024 * 1024
    }
    return file_size <= plan_limits.get(user.plan_id, 10 * 1024 * 1024)

# -----------------------------
# Endpoints
# -----------------------------
@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    analysis_type: str = "full",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    start_time = time.time()

    # Request limit check
    if user.monthly_requests >= user.request_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monthly request limit exceeded"
        )

    contents = await file.read()
    if not check_file_size_limit(len(contents), user):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large for your plan"
        )

    dataset_hash = generate_dataset_hash(contents)

    # Parse CSV
    try:
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
    except Exception:
        df = pd.read_csv(io.BytesIO(contents))

    if df.empty or len(df.columns) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or has no columns"
        )

    analyzer = EnhancedDataAnalyzer(df)
    report = analyzer.generate_complete_report(analysis_type)
    processing_time = int((time.time() - start_time) * 1000)

    user.monthly_requests += 1

    db_report = AnalysisReport(
        user_id=user.id,
        dataset_name=file.filename,
        dataset_hash=dataset_hash,
        summary=report.get("summary", {}),
        patterns=report.get("patterns", []),
        recommendations=report.get("recommendations", []),
        processing_time_ms=processing_time
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    return {
        "id": str(db_report.id),
        "dataset_name": file.filename,
        "dataset_hash": dataset_hash,
        "summary": report.get("summary", {}),
        "patterns": report.get("patterns", []),
        "recommendations": report.get("recommendations", []),
        "processing_time_ms": processing_time,
        "requests_remaining": user.request_limit - user.monthly_requests,
        "timestamp": datetime.utcnow().isoformat()
    }

# Otros endpoints como /reports, /reports/{report_id}, /usage, /reports/{report_id} DELETE
# puedes mantener exactamente igual como los tenías
