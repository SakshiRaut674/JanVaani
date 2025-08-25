import requests
import json

# Configuration
BASE_URL = "http://localhost:3000"

def get_auth_token():
    """Get auth token using development OTP"""
    print("🔐 Getting authentication token...")
    
    # Step 1: Send OTP
    mobile = "+917471141860"
    response = requests.post(f"{BASE_URL}/api/auth/send-otp?mobile={mobile}")
    print(f"Send OTP Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Failed to send OTP: {response.text}")
        return None
    
    # Step 2: Verify OTP (using development OTP 123456)
    response = requests.post(f"{BASE_URL}/api/auth/verify-otp?mobile={mobile}&otp=123456")
    print(f"Verify OTP Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        token = data.get('token')
        print(f"✅ Token obtained: {token[:50]}...")
        return token
    else:
        print(f"Failed to verify OTP: {response.text}")
        return None

def test_bills_api(token):
    """Test bills API"""
    print("\n📋 Testing Bills API...")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test bills endpoint
    response = requests.get(f"{BASE_URL}/revenue/bills", headers=headers)
    print(f"Bills API Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Found {data.get('total_count', 0)} bills")
        if data.get('bills'):
            for bill in data['bills'][:3]:  # Show first 3 bills
                print(f"- {bill.get('bill_type', 'Unknown')}: ₹{bill.get('amount', 0)} ({bill.get('status', 'unknown')})")
        return data
    else:
        print(f"❌ Bills API Error: {response.text}")
        return None

def create_default_bills(token):
    """Create default bills for user"""
    print("\n🏗️ Creating default bills...")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.post(f"{BASE_URL}/revenue/check-and-create-bills", headers=headers)
    print(f"Create Bills Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ {data}")
        return True
    else:
        print(f"❌ Create Bills Error: {response.text}")
        return False

def main():
    print("🚀 Testing Bills and Payment System...")
    print("=" * 60)
    
    # Get authentication token
    token = get_auth_token()
    if not token:
        print("❌ Failed to get authentication token")
        return
    
    # Test bills API
    bills_data = test_bills_api(token)
    
    # If no bills, create default ones
    if not bills_data or bills_data.get('total_count', 0) == 0:
        print("📝 No bills found, creating default bills...")
        create_default_bills(token)
        # Test again after creating bills
        test_bills_api(token)
    
    print("\n✅ Bills system test completed!")

if __name__ == "__main__":
    main()
