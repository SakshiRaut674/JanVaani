#!/usr/bin/env python3

import requests
import json

def test_certificate_payment_update():
    """Test the certificate payment update endpoint"""
    base_url = "http://localhost:3000"
    
    print("🧪 Testing Certificate Payment Update API")
    print("=" * 50)
    
    try:
        # Step 1: Login to get token
        print("1️⃣ Logging in...")
        otp_response = requests.post(f"{base_url}/auth/send-otp", json={"mobile": "+919876543210"})
        
        if otp_response.status_code != 200:
            print(f"   Error sending OTP: {otp_response.text}")
            return
        
        verify_response = requests.post(f"{base_url}/auth/verify-otp", json={
            "mobile": "+919876543210",
            "otp": "123456",
            "userData": {
                "mobile": "+919876543210",
                "email": "testuser@example.com",
                "name": "Test User"
            }
        })
        
        if verify_response.status_code != 200:
            print(f"   Error verifying OTP: {verify_response.text}")
            return
        
        auth_data = verify_response.json()
        token = auth_data.get("access_token")
        user_id = auth_data.get("user", {}).get("id")
        
        if not token:
            print("   Error: No token received")
            return
        
        print(f"   ✅ Login successful! User ID: {user_id}")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 2: Create a certificate application
        print("2️⃣ Creating certificate application...")
        cert_data = {
            "certificate_type": "birth",
            "applicant_name": "Test User",
            "father_name": "Test Father",
            "mother_name": "Test Mother",
            "date_of_birth": "1990-01-01",
            "place_of_birth": "Test City",
            "supporting_documents": []
        }
        
        cert_response = requests.post(f"{base_url}/certificates/apply", 
                                    headers=headers, 
                                    json=cert_data)
        
        if cert_response.status_code != 200:
            print(f"   Error creating certificate: {cert_response.status_code} {cert_response.text}")
            return
        
        cert_result = cert_response.json()
        application_id = cert_result.get("application_id")
        print(f"   ✅ Certificate created with ID: {application_id}")
        
        # Step 3: Test payment update endpoint
        print("3️⃣ Testing payment update...")
        payment_id = "test_pay_123456"
        payment_status = "paid"
        
        payment_update_url = f"{base_url}/certificates/payment/update"
        params = {
            "application_id": application_id,
            "payment_id": payment_id,
            "payment_status": payment_status
        }
        
        payment_response = requests.post(payment_update_url, 
                                       headers=headers,
                                       params=params)
        
        print(f"   Status Code: {payment_response.status_code}")
        
        if payment_response.status_code == 200:
            print("   ✅ Payment update successful!")
            result = payment_response.json()
            print(f"   Response: {json.dumps(result, indent=2)}")
        else:
            print(f"   ❌ Payment update failed: {payment_response.text}")
        
        # Step 4: Verify the certificate was updated
        print("4️⃣ Verifying certificate status...")
        cert_check_response = requests.get(f"{base_url}/certificates/user/{user_id}", 
                                         headers=headers)
        
        if cert_check_response.status_code == 200:
            cert_data = cert_check_response.json()
            applications = cert_data.get("applications", [])
            
            updated_cert = next((app for app in applications if app.get("application_id") == application_id), None)
            
            if updated_cert:
                print(f"   Certificate Payment Status: {updated_cert.get('payment_status', 'N/A')}")
                print(f"   Certificate Status: {updated_cert.get('status', 'N/A')}")
                print(f"   Payment ID: {updated_cert.get('payment_id', 'N/A')}")
                
                if updated_cert.get('payment_status') == payment_status:
                    print("   ✅ Payment status updated correctly!")
                else:
                    print("   ❌ Payment status not updated")
            else:
                print("   ❌ Certificate not found")
        else:
            print(f"   Error checking certificate: {cert_check_response.text}")
        
        print("\n📋 Test Summary:")
        print(f"Application ID: {application_id}")
        print(f"Payment ID: {payment_id}")
        print(f"Payment Status: {payment_status}")
        print("\n✅ Certificate payment update test completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to backend server.")
        print("   Make sure the Python backend is running on http://localhost:3000")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    test_certificate_payment_update()
