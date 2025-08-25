import requests
import json

def get_fresh_token():
    """Get a fresh authentication token"""
    mobile = '+917471141860'
    
    # Send OTP
    send_response = requests.post(f'http://localhost:3000/api/auth/send-otp?mobile={mobile}')
    print(f"Send OTP: {send_response.status_code}")
    
    # Verify OTP
    verify_response = requests.post(f'http://localhost:3000/api/auth/verify-otp?mobile={mobile}&otp=123456')
    print(f"Verify OTP: {verify_response.status_code}")
    
    if verify_response.status_code == 200:
        token = verify_response.json().get('token')
        print(f"✅ Fresh token obtained: {token[:50]}...")
        return token
    else:
        print(f"❌ Auth failed: {verify_response.text}")
        return None

def test_bills_frontend():
    """Test bills frontend API"""
    print("\n📋 Testing Bills Frontend API...")
    token = get_fresh_token()
    if not token:
        return
    
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('http://localhost:3001/api/revenue?endpoint=summary', headers=headers)
    print(f"Bills API Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Bills Summary:")
        print(f"  - Property taxes: {len(data.get('property_taxes', []))} bills")
        print(f"  - Water taxes: {len(data.get('water_taxes', []))} bills")  
        print(f"  - Garbage taxes: {len(data.get('garbage_taxes', []))} bills")
        print(f"  - Total pending: ₹{data.get('total_pending', 0)}")
        print(f"  - Total overdue: ₹{data.get('total_overdue', 0)}")
        return True
    else:
        print(f"❌ Bills API Error: {response.text}")
        return False

def test_certificate_apply():
    """Test certificate application API"""
    print("\n📜 Testing Certificate Application API...")
    token = get_fresh_token()
    if not token:
        return
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    certificate_data = {
        "certificate_type": "birth",
        "applicant_name": "Test User",
        "applicant_address": "Test Address, Bhopal",
        "is_urgent": False,
        "certificate_data": {
            "child_name": "Test Child",
            "date_of_birth": "2023-05-15",
            "place_of_birth": "Test Hospital",
            "father_name": "Test Father",
            "mother_name": "Test Mother",
            "permanent_address": "Test Address"
        },
        "documents": []
    }
    
    response = requests.post('http://localhost:3001/api/certificates/apply', 
                           headers=headers, json=certificate_data)
    print(f"Certificate Apply Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        data = response.json()
        print(f"✅ Certificate Application Created:")
        print(f"  - Application ID: {data.get('application_id', 'N/A')}")
        print(f"  - Fee Amount: ₹{data.get('fee_amount', 0)}")
        print(f"  - Payment Required: {data.get('payment_required', False)}")
        return True
    else:
        print(f"❌ Certificate Apply Error: {response.text}")
        return False

def main():
    print("🚀 Testing Bills & Certificate System...")
    print("=" * 60)
    
    bills_ok = test_bills_frontend()
    cert_ok = test_certificate_apply()
    
    print("\n📊 Test Results:")
    print(f"Bills Frontend API: {'✅ Working' if bills_ok else '❌ Failed'}")
    print(f"Certificate Apply API: {'✅ Working' if cert_ok else '❌ Failed'}")
    
    if bills_ok and cert_ok:
        print("\n🎉 All systems are working! The dashboard should show bills and certificate applications should work.")
    else:
        print("\n⚠️ Some issues found. Check the errors above.")

if __name__ == "__main__":
    main()
