import asyncio, sys
sys.path.append('C:/Users/priya/OneDrive/Desktop/EE')
from fastapi_app import health_check

async def main():
    response = await health_check()
    print('status_code', response.status_code)
    print('body', response.body)

asyncio.run(main())

