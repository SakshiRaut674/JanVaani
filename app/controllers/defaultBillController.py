# app/controllers/defaultBillController.py
from app.models.bill_model import BillCreateModel, BillType, BillStatus, BillPriority
from app.controllers.billController import create_bill_for_user
from datetime import datetime, timedelta
import random

async def create_default_bills_for_new_user(user_data: dict):
    """
    Create default bills for a new user based on their location and profile.
    This should be called when a user registers or logs in for the first time.
    """
    try:
        user_id = user_data.get("id")
        user_phone = user_data.get("mobile", "+919999999999")
        user_address = user_data.get("address", "Default Address, Bhopal, MP")
        
        # Define default bills that every citizen should have
        default_bills = [
            {
                "bill_type": BillType.PROPERTY_TAX,
                "description": "Annual Property Tax",
                "base_amount": 12000.0,
                "months_overdue": 2,  # Make it overdue to show urgency
                "priority": BillPriority.HIGH
            },
            {
                "bill_type": BillType.WATER_BILL,
                "description": "Monthly Water Supply Bill",
                "base_amount": 500.0,
                "months_overdue": 1,
                "priority": BillPriority.MEDIUM
            },
            {
                "bill_type": BillType.GARBAGE_FEE,
                "description": "Waste Management Fee",
                "base_amount": 300.0,
                "months_overdue": 0,  # Current bill
                "priority": BillPriority.LOW
            },
            {
                "bill_type": BillType.PROPERTY_TAX,
                "description": "Property Tax - Previous Year",
                "base_amount": 11500.0,
                "months_overdue": 14,  # Very overdue
                "priority": BillPriority.HIGH
            },
            {
                "bill_type": BillType.SEWAGE_FEE,
                "description": "Sewage Treatment Fee",
                "base_amount": 800.0,
                "months_overdue": 0,
                "priority": BillPriority.MEDIUM
            }
        ]
        
        created_bills = []
        
        for bill_template in default_bills:
            # Calculate due date based on months overdue
            if bill_template["months_overdue"] > 0:
                due_date = datetime.now() - timedelta(days=bill_template["months_overdue"] * 30)
                status = BillStatus.OVERDUE
                # Add penalty for overdue bills
                penalty = bill_template["base_amount"] * 0.02 * bill_template["months_overdue"]  # 2% per month
            else:
                due_date = datetime.now() + timedelta(days=30)  # Due in 30 days
                status = BillStatus.PENDING
                penalty = 0.0
            
            # Create bill
            bill_data = BillCreateModel(
                bill_type=bill_template["bill_type"],
                description=bill_template["description"],
                amount=bill_template["base_amount"] + penalty,
                due_date=due_date,
                year=str(datetime.now().year),
                period=f"{datetime.now().strftime('%B %Y')}",
                late_fee=0.0,
                penalty=penalty,
                discount=0.0,
                metadata={
                    "auto_generated": True,
                    "user_type": "new_user",
                    "generation_date": datetime.now().isoformat(),
                    "base_amount": bill_template["base_amount"],
                    "months_overdue": bill_template["months_overdue"]
                }
            )
            
            # Create the bill
            try:
                created_bill = await create_bill_for_user(bill_data, user_data)
                created_bills.append(created_bill)
                print(f"✅ Created {bill_template['bill_type']} bill for user {user_id}")
            except Exception as e:
                print(f"❌ Failed to create {bill_template['bill_type']} bill: {e}")
                continue
        
        return {
            "success": True,
            "message": f"Created {len(created_bills)} default bills for user",
            "bills_created": len(created_bills),
            "bills": created_bills
        }
        
    except Exception as e:
        print(f"Error creating default bills for user: {e}")
        return {
            "success": False,
            "message": f"Failed to create default bills: {str(e)}",
            "bills_created": 0,
            "bills": []
        }

async def check_and_create_default_bills(user_data: dict):
    """
    Check if user has any bills, if not create default bills.
    This can be called on login to ensure every user has some bills.
    """
    try:
        from app.controllers.billController import get_user_bills_count
        
        # Check if user already has bills
        bill_count = await get_user_bills_count(user_data)
        
        if bill_count == 0:
            print(f"User {user_data.get('id')} has no bills. Creating default bills...")
            return await create_default_bills_for_new_user(user_data)
        else:
            print(f"User {user_data.get('id')} already has {bill_count} bills.")
            return {
                "success": True,
                "message": f"User already has {bill_count} bills",
                "bills_created": 0,
                "existing_bills": bill_count
            }
            
    except Exception as e:
        print(f"Error checking/creating default bills: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "bills_created": 0
        }

async def create_bills_for_location(user_data: dict, city: str, state: str):
    """
    Create location-specific bills based on user's city and state.
    Different cities might have different types of taxes and fees.
    """
    location_specific_bills = {
        "bhopal": [
            {"type": BillType.PROPERTY_TAX, "base_rate": 15000, "description": "Bhopal Property Tax"},
            {"type": BillType.WATER_BILL, "base_rate": 600, "description": "Bhopal Water Supply"},
            {"type": BillType.GARBAGE_FEE, "base_rate": 400, "description": "Bhopal Waste Management"}
        ],
        "indore": [
            {"type": BillType.PROPERTY_TAX, "base_rate": 18000, "description": "Indore Property Tax"},
            {"type": BillType.WATER_BILL, "base_rate": 700, "description": "Indore Water Supply"},
            {"type": BillType.GARBAGE_FEE, "base_rate": 500, "description": "Indore Waste Management"}
        ],
        "default": [
            {"type": BillType.PROPERTY_TAX, "base_rate": 12000, "description": "Property Tax"},
            {"type": BillType.WATER_BILL, "base_rate": 500, "description": "Water Supply"},
            {"type": BillType.GARBAGE_FEE, "base_rate": 300, "description": "Waste Management"}
        ]
    }
    
    city_key = city.lower() if city else "default"
    bills_template = location_specific_bills.get(city_key, location_specific_bills["default"])
    
    created_bills = []
    for bill_template in bills_template:
        # Create bill with location-specific rates
        bill_data = BillCreateModel(
            bill_type=bill_template["type"],
            description=bill_template["description"],
            amount=bill_template["base_rate"],
            due_date=datetime.now() + timedelta(days=30),
            year=str(datetime.now().year),
            period=f"{datetime.now().strftime('%B %Y')}",
            late_fee=0.0,
            penalty=0.0,
            discount=0.0,
            metadata={
                "location_based": True,
                "city": city,
                "state": state,
                "auto_generated": True
            }
        )
        
        try:
            created_bill = await create_bill_for_user(bill_data, user_data)
            created_bills.append(created_bill)
        except Exception as e:
            print(f"Failed to create location-specific bill: {e}")
            continue
    
    return created_bills
