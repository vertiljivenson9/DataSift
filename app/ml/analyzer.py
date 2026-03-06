"""
ML Analysis API - Enterprise-grade data analysis with machine learning
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import pandas as pd
import io
import time
import hashlib
import json

from ..auth import get_current_user
from ..database import get_db
from ..models import User, AnalysisReport
from .enhanced_analyzer import EnhancedDataAnalyzer

router = APIRouter()


# Pydantic models for API responses
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


def generate_dataset_hash(content: bytes) -> str:
    """Generate MD5 hash of dataset content"""
    return hashlib.sha256(content).hexdigest()[:32]


def check_file_size_limit(file_size: int, user: User) -> bool:
    """Check if file size is within user's plan limits"""
    plan_limits = {
        "free": 10 * 1024 * 1024,      # 10 MB
        "pro": 100 * 1024 * 1024,      # 100 MB
        "enterprise": 500 * 1024 * 1024  # 500 MB
    }
    limit = plan_limits.get(user.plan_id, 10 * 1024 * 1024)
    return file_size <= limit


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="Analyze dataset",
    description="Upload and analyze a CSV file using machine learning algorithms",
    responses={
        200: {"description": "Analysis completed successfully"},
        400: {"description": "Invalid file format"},
        429: {"description": "Rate limit exceeded"},
        413: {"description": "File too large"}
    }
)
async def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file to analyze"),
    analysis_type: str = "full",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze a CSV dataset using machine learning.
    
    - **file**: CSV file to analyze (max size depends on plan)
    - **analysis_type**: Type of analysis - "quick" or "full"
    
    Returns comprehensive analysis including:
    - Statistical summary
    - Detected patterns (outliers, clusters)
    - Actionable recommendations
    """
    start_time = time.time()
    
    # Check request limit
    if user.monthly_requests >= user.request_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Monthly request limit exceeded",
                "limit": user.request_limit,
                "used": user.monthly_requests,
                "upgrade_url": "/pricing"
            }
        )
    
    # Read file content
    contents = await file.read()
    file_size = len(contents)
    
    # Check file size limit
    if not check_file_size_limit(file_size, user):
        plan_limits = {"free": "10MB", "pro": "100MB", "enterprise": "500MB"}
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "File size exceeds plan limit",
                "file_size": f"{file_size / (1024*1024):.2f}MB",
                "plan_limit": plan_limits.get(user.plan_id, "10MB"),
                "upgrade_url": "/pricing"
            }
        )
    
    # Generate dataset hash
    dataset_hash = generate_dataset_hash(contents)
    
    # Parse CSV
    try:
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(io.BytesIO(contents))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid CSV file", "message": str(e)}
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Failed to parse CSV", "message": str(e)}
        )
    
    # Validate dataframe
    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "CSV file is empty"}
        )
    
    if len(df.columns) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "CSV file has no columns"}
        )
    
    # Perform analysis
    analyzer = EnhancedDataAnalyzer(df)
    report = analyzer.generate_complete_report(analysis_type)
    
    processing_time = int((time.time() - start_time) * 1000)
    
    # Increment user request count
    user.monthly_requests += 1
    
    # Save report to database
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


@router.get(
    "/reports",
    response_model=List[ReportSummary],
    summary="List analysis reports",
    description="Get a list of recent analysis reports for the authenticated user"
)
async def get_reports(
    limit: int = 10,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of analysis reports"""
    reports = db.query(AnalysisReport).filter(
        AnalysisReport.user_id == user.id
    ).order_by(
        AnalysisReport.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    return [{
        "id": str(r.id),
        "dataset_name": r.dataset_name,
        "created_at": r.created_at.isoformat(),
        "processing_time_ms": r.processing_time_ms
    } for r in reports]


@router.get(
    "/reports/{report_id}",
    response_model=AnalysisResponse,
    summary="Get report details",
    description="Get detailed information about a specific analysis report"
)
async def get_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific report details"""
    from uuid import UUID
    
    try:
        report_uuid = UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report ID format"
        )
    
    report = db.query(AnalysisReport).filter(
        AnalysisReport.id == report_uuid,
        AnalysisReport.user_id == user.id
    ).first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    return {
        "id": str(report.id),
        "dataset_name": report.dataset_name,
        "dataset_hash": report.dataset_hash or "",
        "summary": report.summary or {},
        "patterns": report.patterns or [],
        "recommendations": report.recommendations or [],
        "processing_time_ms": report.processing_time_ms or 0,
        "requests_remaining": user.request_limit - user.monthly_requests,
        "timestamp": report.created_at.isoformat()
    }


@router.get(
    "/usage",
    response_model=UsageStats,
    summary="Get usage statistics",
    description="Get current usage statistics for the authenticated user"
)
async def get_usage(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user usage statistics"""
    total_reports = db.query(AnalysisReport).filter(
        AnalysisReport.user_id == user.id
    ).count()
    
    usage_percentage = round((user.monthly_requests / user.request_limit) * 100, 2) if user.request_limit > 0 else 0
    
    return {
        "total_requests": total_reports,
        "requests_this_month": user.monthly_requests,
        "request_limit": user.request_limit,
        "usage_percentage": usage_percentage,
        "datasets_analyzed": total_reports
    }


@router.delete(
    "/reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete report",
    description="Delete a specific analysis report"
)
async def delete_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a report"""
    from uuid import UUID
    
    try:
        report_uuid = UUID(report_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report ID format"
        )
    
    report = db.query(AnalysisReport).filter(
        AnalysisReport.id == report_uuid,
        AnalysisReport.user_id == user.id
    ).first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    db.delete(report)
    db.commit()
    
    return None
