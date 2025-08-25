import requests

# Get fresh token
mobile = '+917471141860'
requests.post(f'http://localhost:3000/api/auth/send-otp?mobile={mobile}')
response = requests.post(f'http://localhost:3000/api/auth/verify-otp?mobile={mobile}&otp=123456')

if response.status_code == 200:
    token = response.json().get('token')
    print(f'Testing frontend API with fresh token...')
    
    # Test frontend proxy with transformation
    headers = {'Authorization': f'Bearer {token}'}
    frontend_response = requests.get('http://localhost:3001/api/revenue?endpoint=summary', headers=headers)
    print(f'Frontend API status: {frontend_response.status_code}')
    
    if frontend_response.status_code == 200:
        data = frontend_response.json()
        print(f'Property taxes: {len(data.get("property_taxes", []))}')
        print(f'Water taxes: {len(data.get("water_taxes", []))}')  
        print(f'Garbage taxes: {len(data.get("garbage_taxes", []))}')
        print(f'Total pending: ₹{data.get("total_pending", 0)}')
        print(f'Total overdue: ₹{data.get("total_overdue", 0)}')
        
        # Show sample bills
        if data.get("property_taxes"):
            print(f'Sample property tax: {data["property_taxes"][0]}')
        if data.get("water_taxes"):
            print(f'Sample water tax: {data["water_taxes"][0]}')
    else:
        print(f'Error: {frontend_response.text}')
else:
    print('Auth failed')
