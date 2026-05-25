"""Quick check: verify test01 password"""
import asyncio
from sqlalchemy import select
from app.db.database import async_session_factory
from app.models.user import User
from app.auth.security import verify_password

async def check():
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.username == 'test01'))
        user = result.scalar_one_or_none()
        if user:
            print(f'Hash prefix: {user.hashed_password[:60]}')
            for pw in ['test01', 'Test01', '123456', 'password', 'Test01!']:
                ok = verify_password(pw, user.hashed_password)
                print(f'  password="{pw}": {ok}')
        else:
            print('User not found')

asyncio.run(check())
