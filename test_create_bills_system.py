import requests
import json

print("🔧 Testing Create Sample Bills System...")
print("=" * 60)

# Test authentication first
print("🔐 Testing Authentication...")
otp_data = {'mobile': '9999999999'}
otp_response = requests.post('http://127.0.0.1:3000/auth/send-otp', json=otp_data)
print(f"Send OTP (auth prefix): {otp_response.status_code}")

if otp_response.status_code == 404:
    # Try without auth prefix
    otp_response = requests.post('http://127.0.0.1:3000/send-otp', json=otp_data)
    print(f"Send OTP (no prefix): {otp_response.status_code}")

if otp_response.status_code == 200:
    verify_data = {'mobile': '9999999999', 'otp': '123456'}
    verify_response = requests.post('http://127.0.0.1:3000/verify-otp', json=verify_data)
    print(f"Verify OTP: {verify_response.status_code}")
    
    if verify_response.status_code == 200:
        token_data = verify_response.json()
        token = token_data['data']['access_token']
        print(f"✅ Got token: {token[:20]}...")
        
        # Test backend create sample taxes directly
        print("\n📋 Testing Backend Create Sample Taxes...")
        headers = {'Authorization': f'Bearer {token}'}
        taxes_response = requests.post('http://127.0.0.1:3000/revenue/create-sample-taxes', headers=headers)
        print(f"Backend Response: {taxes_response.status_code}")
        print(f"Backend Content: {taxes_response.text}")
        
        # Test Next.js API route
        print("\n🌐 Testing Next.js API Route...")
        frontend_response = requests.post('http://localhost:3001/api/revenue/create-sample-taxes', headers=headers)
        print(f"Frontend API Response: {frontend_response.status_code}")
        print(f"Frontend API Content: {frontend_response.text}")
        
        # Test bills retrieval
        print("\n📄 Testing Bills Retrieval...")
        bills_response = requests.get('http://localhost:3001/api/revenue', headers=headers)
        print(f"Bills API Response: {bills_response.status_code}")
        if bills_response.status_code == 200:
            bills_data = bills_response.json()
            print(f"Bills found: {len(bills_data.get('bills', []))}")
        
    else:
        print(f"❌ OTP verification failed: {verify_response.text}")
else:
    print(f"❌ Send OTP failed: {otp_response.text}")
