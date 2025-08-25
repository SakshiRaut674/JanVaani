import requests

# Get fresh token
mobile = '+917471141860'
requests.post(f'http://localhost:3000/api/auth/send-otp?mobile={mobile}')
response = requests.post(f'http://localhost:3000/api/auth/verify-otp?mobile={mobile}&otp=123456')

if response.status_code == 200:
    token = response.json().get('token')
    print(f'Fresh token: {token[:50]}...')
    
    # Test revenue API
    headers = {'Authorization': f'Bearer {token}'}
    bills_response = requests.get('http://localhost:3000/revenue/summary', headers=headers)
    print(f'Backend revenue API status: {bills_response.status_code}')
    
    if bills_response.status_code == 200:
        data = bills_response.json()
        print(f'Backend bills summary: {data}')
        
        # Test frontend proxy
        frontend_response = requests.get('http://localhost:3001/api/revenue?endpoint=summary', headers=headers)
        print(f'Frontend proxy status: {frontend_response.status_code}')
        if frontend_response.status_code == 200:
            frontend_data = frontend_response.json()
            print(f'Frontend bills summary: {frontend_data}')
        else:
            print(f'Frontend error: {frontend_response.text}')
    else:
        print(f'Backend error: {bills_response.text}')
else:
    print(f'Auth failed: {response.text}')
