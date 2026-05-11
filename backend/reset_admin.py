import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# 导入你的模型和配置
# 注意：这里我们手动定义一些必要的逻辑，以防导入路径在脚本中失效
from app.config import settings
from app.models.user import User, UserRole
from app.db.base import Base

# 初始化密码哈希工具 (与后端一致)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def reset_admin():
    print(f"🔗 正在连接数据库: {settings.database_url}")
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. 查找现有 admin
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalars().first()

        hashed_password = pwd_context.hash("admin123")

        if user:
            print(f"👤 发现现有用户: {user.username}，正在重置密码...")
            user.hashed_password = hashed_password
            user.role = UserRole.ADMIN
            user.is_active = True
        else:
            print("🆕 未发现 admin 用户，正在创建...")
            user = User(
                id=uuid.uuid4(),
                username="admin",
                email="admin@yibiao.ai",
                hashed_password=hashed_password,
                role=UserRole.ADMIN,
                is_active=True
            )
            session.add(user)
        
        await session.commit()
        print("✅ 成功！现在你可以使用 admin / admin123 登录了。")

if __name__ == "__main__":
    asyncio.run(reset_admin())
