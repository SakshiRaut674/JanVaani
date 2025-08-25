import requests
import json

# Get fresh token
otp_data = {'mobile': '9999999999'}
otp_response = requests.post('http://127.0.0.1:3000/send-otp', json=otp_data)
print(f'Send OTP: {otp_response.status_code}')

verify_data = {'mobile': '9999999999', 'otp': '123456'}
verify_response = requests.post('http://127.0.0.1:3000/verify-otp', json=verify_data)
print(f'Verify OTP: {verify_response.status_code}')

if verify_response.status_code == 200:
    token_data = verify_response.json()
    token = token_data['data']['access_token']
    print(f'Got token: {token[:20]}...')
    
    # Test create sample taxes
    headers = {'Authorization': f'Bearer {token}'}
    taxes_response = requests.post('http://127.0.0.1:3000/revenue/create-sample-taxes', headers=headers)
    print(f'Create sample taxes: {taxes_response.status_code}')
    print(f'Response: {taxes_response.text}')
