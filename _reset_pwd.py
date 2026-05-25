"""Reset test01 password to 'test01'"""
import asyncio
from sqlalchemy import select, update
from app.db.database import async_session_factory
from app.models.user import User
from app.auth.security import get_password_hash, verify_password

async def reset_pwd():
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.username == 'test01'))
        user = result.scalar_one_or_none()
        if user:
            new_hash = get_password_hash('test01')
            print(f'New hash: {new_hash}')
            # Verify before saving
            assert verify_password('test01', new_hash), "Hash verification failed!"
            
            await session.execute(
                update(User)
                .where(User.username == 'test01')
                .values(hashed_password=new_hash)
            )
            await session.commit()
            print(f"✅ test01 password reset to 'test01'")
            
            # Re-verify from DB
            result2 = await session.execute(select(User).where(User.username == 'test01'))
            user2 = result2.scalar_one_or_none()
            print(f'DB verify: {verify_password("test01", user2.hashed_password)}')
        else:
            print('User not found')

asyncio.run(reset_pwd())
