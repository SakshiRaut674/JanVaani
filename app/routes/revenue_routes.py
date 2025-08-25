# app/routes/revenue_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from app.middlewares.authMiddleware import get_current_user
from app.controllers.billController import (
    get_user_bills, get_bill_by_id, create_sample_bills, 
    update_bill_status
)
from app.controllers.paymentController import (
    create_payment_record, update_payment_status, get_user_payment_history,
    get_payment_by_id, get_payment_statistics, verify_razorpay_payment
)
from app.models.bill_model import BillSearchModel, BillUpdateModel
from app.models.payment_model import PaymentCreateModel, PaymentUpdateModel, PaymentStatus
from typing import Optional
import datetime

router = APIRouter(tags=["Revenue"])

@router.get("/summary")
async def get_revenue_summary(current_user: dict = Depends(get_current_user)):
    """Get comprehensive revenue summary for the current user"""
    try:
        # Get bills summary with real database data
        bills_response = await get_user_bills(current_user, page=1, limit=100)
        bills_data = bills_response.body
        
        # Parse the response content if it's a JSONResponse
        if hasattr(bills_data, 'decode'):
            import json
            bills_data = json.loads(bills_data.decode())
        
        return bills_data
        
    except Exception as e:
        print(f"Error fetching revenue summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching revenue summary: {str(e)}")

@router.get("/bills")
async def get_bills(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    bill_type: Optional[str] = None,
    status: Optional[str] = None,
    search_term: Optional[str] = None,
    year: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get user's bills with filters and pagination"""
    try:
        # Build search criteria
        search = BillSearchModel(
            search_term=search_term,
            bill_type=bill_type,
            status=status,
            year=year
        )
        
        return await get_user_bills(current_user, page, limit, search)
        
    except Exception as e:
        print(f"Error fetching bills: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching bills: {str(e)}")

@router.get("/bills/{bill_id}")
async def get_bill_details(
    bill_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed information for a specific bill"""
    return await get_bill_by_id(bill_id, current_user)

@router.post("/bills/sample")
async def create_sample_bills_endpoint(current_user: dict = Depends(get_current_user)):
    """Create sample bills for testing"""
    return await create_sample_bills(current_user)

@router.post("/create-sample-taxes")
async def create_sample_taxes_endpoint(current_user: dict = Depends(get_current_user)):
    """Create sample taxes for testing - legacy endpoint for frontend compatibility"""
    return await create_sample_bills(current_user)

@router.post("/create-default-bills")
async def create_default_bills_endpoint(current_user: dict = Depends(get_current_user)):
    """Create default bills for a new user"""
    try:
        from app.controllers.defaultBillController import create_default_bills_for_new_user
        return await create_default_bills_for_new_user(current_user)
    except Exception as e:
        print(f"Error creating default bills: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create default bills: {str(e)}")

@router.post("/check-and-create-bills")
async def auto_create_bills_if_needed(current_user: dict = Depends(get_current_user)):
    """Check if user has bills, create default ones if not"""
    try:
        from app.controllers.defaultBillController import check_and_create_default_bills
        return await check_and_create_default_bills(current_user)
    except Exception as e:
        print(f"Error in auto bill creation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check/create bills: {str(e)}")

@router.post("/bills/{bill_id}/pay")
async def initiate_bill_payment(
    bill_id: str,
    payment_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Initiate payment for a bill"""
    try:
        # Get bill details first
        bill_response = await get_bill_by_id(bill_id, current_user)
        
        # Parse bill data
        if hasattr(bill_response.body, 'decode'):
            import json
            bill_data = json.loads(bill_response.body.decode())
            bill = bill_data["bill"]
        else:
            bill = bill_response.body["bill"]
        
        # Check if bill is already paid
        if bill["status"] == "paid":
            raise HTTPException(
                status_code=400, 
                detail="Bill is already paid"
            )
        
        # Create payment record
        payment_create = PaymentCreateModel(
            service_type=bill["bill_type"],
            service_id=bill["bill_id"],
            amount=bill["balance_amount"],
            payment_method=payment_data.get("payment_method", "online"),
            razorpay_order_id=payment_data.get("razorpay_order_id"),
            description=f"Payment for {bill['description']}",
            metadata={
                "bill_id": bill["bill_id"],
                "bill_type": bill["bill_type"],
                "due_date": bill["due_date"]
            }
        )
        
        return await create_payment_record(payment_create, current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error initiating bill payment: {e}")
        raise HTTPException(status_code=500, detail=f"Error initiating payment: {str(e)}")

@router.post("/payments/verify")
async def verify_bill_payment(
    verification_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Verify payment after successful Razorpay transaction"""
    try:
        razorpay_order_id = verification_data.get("razorpay_order_id")
        razorpay_payment_id = verification_data.get("razorpay_payment_id")
        razorpay_signature = verification_data.get("razorpay_signature")
        payment_id = verification_data.get("payment_id")
        
        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, payment_id]):
            raise HTTPException(
                status_code=400, 
                detail="Missing required payment verification data"
            )
        
        # Verify payment signature (skip for mock payments)
        if not (razorpay_order_id.startswith("order_mock_") or razorpay_payment_id.startswith("pay_mock_")):
            is_valid = await verify_razorpay_payment(
                razorpay_order_id, razorpay_payment_id, razorpay_signature
            )
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid payment signature"
                )
        
        # Update payment status to success
        payment_update = PaymentUpdateModel(
            status=PaymentStatus.SUCCESS,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature
        )
        
        return await update_payment_status(payment_id, payment_update, current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error verifying payment: {e}")
        raise HTTPException(status_code=500, detail=f"Error verifying payment: {str(e)}")

@router.get("/payment-history")
async def get_payment_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    service_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get user's payment history with filters"""
    return await get_user_payment_history(
        current_user=current_user, 
        page=page, 
        limit=limit, 
        service_type=service_type, 
        payment_status=status
    )

@router.get("/payments/{payment_id}")
async def get_payment_details(
    payment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed information for a specific payment"""
    return await get_payment_by_id(payment_id, current_user)

@router.get("/statistics")
async def get_revenue_statistics(current_user: dict = Depends(get_current_user)):
    """Get comprehensive payment and bill statistics"""
    return await get_payment_statistics(current_user)

@router.post("/pay")
async def process_bill_payment(
    payment_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Legacy endpoint for bill payment processing"""
    try:
        # For backward compatibility with existing frontend code
        bill_id = payment_data.get("bill_id") or payment_data.get("service_id")
        if not bill_id:
            raise HTTPException(
                status_code=400,
                detail="Missing bill_id or service_id"
            )
        
        return await initiate_bill_payment(bill_id, payment_data, current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing payment: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing payment: {str(e)}")
