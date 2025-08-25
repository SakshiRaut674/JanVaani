import sys
sys.path.append('.')
from app.controllers.billController import create_sample_bills
from app.database.database import get_users_collection
import asyncio

async def test():
    # Mock user
    user = {'_id': '68abc9146e73542301ea2839', 'mobile': '9999999999'}
    try:
        result = await create_sample_bills(user)
        print('Success:', result)
    except Exception as e:
        print('Error:', e)
        import traceback
        traceback.print_exc()

asyncio.run(test())
