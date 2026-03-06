import os
import requests
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
from . import models, database, auth

router = APIRouter()
logger = logging.getLogger(__name__)

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")
PAYPAL_API_BASE = "https://api-m.sandbox.paypal.com" if PAYPAL_MODE == "sandbox" else "https://api-m.paypal.com"

if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
    logger.warning("PayPal credentials not configured. Payment features will be disabled.")

class CreatePaymentRequest(BaseModel):
    plan_id: str
    billing_cycle: str = "monthly"

class PaymentResponse(BaseModel):
    order_id: str
    approval_url: str
    status: str

class PaymentSuccessResponse(BaseModel):
    success: bool
    message: str
    transaction_id: str
    plan: str
    amount: float
    currency: str

def get_paypal_access_token() -> str:
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        raise HTTPException(status_code=503, detail="Payment service temporarily unavailable")
    try:
        auth = (PAYPAL_CLIENT_ID, PAYPAL_SECRET)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials"}
        response = requests.post(f"{PAYPAL_API_BASE}/v1/oauth2/token", auth=auth, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.RequestException as e:
        logger.error(f"PayPal authentication failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Payment service error")

def create_paypal_order(amount: float, description: str, return_url: str, cancel_url: str) -> dict:
    access_token = get_paypal_access_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": f"{amount:.2f}"},
            "description": description
        }],
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "brand_name": "DataSift",
            "landing_page": "BILLING",
            "user_action": "PAY_NOW"
        }
    }
    try:
        response = requests.post(f"{PAYPAL_API_BASE}/v2/checkout/orders", headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"PayPal order creation failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Failed to create payment order")

def capture_paypal_order(order_id: str) -> dict:
    access_token = get_paypal_access_token()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    try:
        response = requests.post(f"{PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture", headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"PayPal capture failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Payment capture failed")

@router.post("/create-payment", response_model=PaymentResponse)
def create_payment(req: CreatePaymentRequest, user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    plan = db.query(models.Plan).filter(models.Plan.id == req.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if user.plan_id == req.plan_id:
        raise HTTPException(status_code=400, detail="You already have this plan")
    amount = plan.price_monthly if req.billing_cycle == "monthly" else plan.price_yearly
    if amount == 0:
        user.plan_id = req.plan_id
        user.request_limit = plan.request_limit
        db.commit()
        return {"order_id": "free", "approval_url": "", "status": "completed"}
    return_url = f"{os.getenv('APP_URL', 'http://localhost:8000')}/payments/success"
    cancel_url = f"{os.getenv('APP_URL', 'http://localhost:8000')}/payments/cancel"
    order = create_paypal_order(amount=amount, description=f"DataSift {plan.name} Plan - {req.billing_cycle.capitalize()}", return_url=return_url, cancel_url=cancel_url)
    payment = models.Payment(user_id=user.id, plan_id=plan.id, amount=amount, currency="USD", paypal_order_id=order["id"], status="pending")
    db.add(payment)
    db.commit()
    approval_link = next((link["href"] for link in order.get("links", []) if link.get("rel") == "approve"), None)
    if not approval_link:
        raise HTTPException(status_code=500, detail="Failed to get approval URL")
    return {"order_id": order["id"], "approval_url": approval_link, "status": "pending"}

@router.get("/success", response_model=PaymentSuccessResponse)
def payment_success(token: str, PayerID: str, db: Session = Depends(database.get_db)):
    payment = db.query(models.Payment).filter(models.Payment.paypal_order_id == token).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status == "completed":
        return {"success": True, "message": "Payment already processed", "transaction_id": payment.paypal_order_id, "plan": payment.plan_id, "amount": payment.amount, "currency": payment.currency}
    try:
        capture_data = capture_paypal_order(token)
    except HTTPException:
        payment.status = "failed"
        db.commit()
        raise
    payment.status = "completed"
    payment.completed_at = datetime.utcnow()
    payment.paypal_payer_id = PayerID
    user = db.query(models.User).filter(models.User.id == payment.user_id).first()
    user.plan_id = payment.plan_id
    user.subscription_status = "active"
    user.subscription_end_date = datetime.utcnow() + timedelta(days=30)
    plan = db.query(models.Plan).filter(models.Plan.id == payment.plan_id).first()
    if plan:
        user.request_limit = plan.request_limit
    db.commit()
    logger.info(f"Payment completed: {token} for user {user.id}, plan {payment.plan_id}")
    return {"success": True, "message": "Payment completed successfully", "transaction_id": payment.paypal_order_id, "plan": payment.plan_id, "amount": payment.amount, "currency": payment.currency}

@router.get("/cancel")
def payment_cancel(token: str, db: Session = Depends(database.get_db)):
    payment = db.query(models.Payment).filter(models.Payment.paypal_order_id == token).first()
    if payment and payment.status == "pending":
        payment.status = "cancelled"
        db.commit()
    return {"success": False, "message": "Payment was cancelled"}

@router.post("/paypal-webhook")
async def paypal_webhook(request: Request, db: Session = Depends(database.get_db)):
    try:
        body = await request.json()
        event_type = body.get("event_type")
        logger.info(f"Received PayPal webhook: {event_type}")
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            resource = body.get("resource", {})
            order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
            if order_id:
                payment = db.query(models.Payment).filter(models.Payment.paypal_order_id == order_id).first()
                if payment and payment.status == "pending":
                    payment.status = "completed"
                    payment.completed_at = datetime.utcnow()
                    user = db.query(models.User).filter(models.User.id == payment.user_id).first()
                    user.plan_id = payment.plan_id
                    user.subscription_end_date = datetime.utcnow() + timedelta(days=30)
                    plan = db.query(models.Plan).filter(models.Plan.id == payment.plan_id).first()
                    if plan:
                        user.request_limit = plan.request_limit
                    db.commit()
                    logger.info(f"Webhook processed: Payment {order_id} completed")
        elif event_type == "PAYMENT.CAPTURE.DENIED":
            resource = body.get("resource", {})
            order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
            if order_id:
                payment = db.query(models.Payment).filter(models.Payment.paypal_order_id == order_id).first()
                if payment:
                    payment.status = "failed"
                    db.commit()
                    logger.warning(f"Webhook: Payment {order_id} denied")
        return {"status": "processed"}
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.get("/history")
def payment_history(user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    payments = db.query(models.Payment).filter(models.Payment.user_id == user.id).order_by(models.Payment.created_at.desc()).all()
    return [{
        "id": str(p.id),
        "plan_id": p.plan_id,
        "amount": p.amount,
        "currency": p.currency,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "completed_at": p.completed_at.isoformat() if p.completed_at else None
    } for p in payments]
