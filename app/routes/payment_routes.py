# app/routes/payment_routes.py
from fastapi import APIRouter, Depends, HTTPException
from app.middlewares.authMiddleware import get_current_user
import hashlib
import hmac
import json
import os
import razorpay

router = APIRouter(tags=["Payments"])

# Razorpay configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_R951wEy8Cp8p21")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "oeHf8W0qTA2PO1SMjt5cb4p7")

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

@router.post("/create-order")
async def create_razorpay_order(
    order_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Create a Razorpay order for payment"""
    try:
        # Extract and validate data
        amount = order_data.get("amount", 0)
        currency = order_data.get("currency", "INR")
        receipt = order_data.get("receipt", f"receipt_{abs(hash(str(order_data)))}")
        
        # Validate required fields
        if not amount or amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid amount")
        
        # Convert amount to paise if needed (Razorpay uses paise)
        if amount < 100:  # If amount is in rupees, convert to paise
            amount = amount * 100
        
        # Create order data for Razorpay
        razorpay_order_data = {
            "amount": int(amount),
            "currency": currency,
            "receipt": receipt,
            "notes": order_data.get("metadata", {})
        }
        
        # Create real Razorpay order
        razorpay_order = razorpay_client.order.create(data=razorpay_order_data)
        
        return {
            "success": True,
            "order": razorpay_order,
            "key_id": RAZORPAY_KEY_ID
        }
        
    except Exception as e:
        print(f"Error creating Razorpay order: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating order: {str(e)}")

@router.post("/create-mock-order")
async def create_mock_order(
    order_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Create a mock order for development testing"""
    try:
        amount = order_data.get("amount", 0)
        currency = order_data.get("currency", "INR")
        receipt = order_data.get("receipt", f"receipt_{hash(str(order_data))}")
        
        # Validate required fields
        if not amount or amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid amount")
        
        # Convert amount to paise if needed
        if amount < 100:
            amount = amount * 100
        
        # Mock Razorpay order response
        mock_order = {
            "id": f"order_mock_{abs(hash(str(order_data) + current_user.get('id', '')))}",
            "entity": "order",
            "amount": int(amount),
            "amount_paid": 0,
            "amount_due": int(amount),
            "currency": currency,
            "receipt": receipt,
            "status": "created",
            "attempts": 0,
            "created_at": 1703097600,
            "notes": order_data.get("metadata", {})
        }
        
        return {
            "success": True,
            "order": mock_order,
            "key_id": RAZORPAY_KEY_ID,
            "mock": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating mock order: {str(e)}")

@router.post("/verify")
async def verify_payment(
    verification_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Verify Razorpay payment signature"""
    try:
        razorpay_order_id = verification_data.get("razorpay_order_id")
        razorpay_payment_id = verification_data.get("razorpay_payment_id")
        razorpay_signature = verification_data.get("razorpay_signature")
        
        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            raise HTTPException(status_code=400, detail="Missing required payment verification data")
        
        # Check if this is a mock payment
        if razorpay_order_id.startswith("order_mock_") or razorpay_payment_id.startswith("pay_mock_"):
            return {
                "verified": True,
                "message": "Mock payment verified successfully",
                "mock": True
            }
        
        # Real payment verification
        verification_params = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        
        # Verify the payment signature
        try:
            razorpay_client.utility.verify_payment_signature(verification_params)
            return {
                "verified": True,
                "message": "Payment verified successfully"
            }
        except razorpay.errors.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid payment signature")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verifying payment: {str(e)}")

@router.post("/webhook")
async def handle_payment_webhook(webhook_data: dict):
    """Handle Razorpay payment webhooks"""
    try:
        # Real webhook handler for Razorpay events
        event = webhook_data.get("event")
        
        if event == "payment.captured":
            payment_entity = webhook_data.get("payload", {}).get("payment", {}).get("entity", {})
            print(f"Payment captured: {payment_entity.get('id')}")
        
        elif event == "payment.failed":
            payment_entity = webhook_data.get("payload", {}).get("payment", {}).get("entity", {})
            print(f"Payment failed: {payment_entity.get('id')}")
        
        return {"status": "webhook processed"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")
