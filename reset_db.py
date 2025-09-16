import asyncio
from sqlalchemy import text
from app.core.database import create_tables, AsyncSessionLocal, engine
from app.core.auth_utils import hash_password
from app.models.user import User, UserStatus


async def reset_database_with_admin():
    """
    Reset database and create admin user (async).
    """
    print("🗑️  Dropping all tables...")
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))

    print("🏗️  Creating fresh tables...")
    await create_tables()

    print("👤 Creating admin user...")
    async with AsyncSessionLocal() as db:
        try:
            # Create admin user
            admin_user = User(
                email="admin@test.com",
                username="admin",
                password_hash=hash_password("admin123456"),
                status=UserStatus.AVAILABLE,
                is_admin=True,
            )

            db.add(admin_user)
            await db.commit()
            await db.refresh(admin_user)

            print(f"✅ Admin user created: {admin_user.email}")
            print(f"   Username: {admin_user.username}")
            print(f"   Is Admin: {admin_user.is_admin}")

            normal_user = User(
                email="user@test.com",
                username="normaluser",
                password_hash=hash_password("user123456"),
                status=UserStatus.AVAILABLE,
                is_admin=False,
            )

            db.add(normal_user)
            await db.commit()
            await db.refresh(normal_user)

            print(f"✅ Normal user created: {normal_user.email}")
            print(f"   Username: {normal_user.username}")
            print(f"   Is Admin: {normal_user.is_admin}")

        except Exception as e:
            print(f"❌ Error: {e}")
            await db.rollback()

    print("\n🚀 Database reset complete!")
    print("\n📝 Test credentials:")
    print("   Admin: admin@test.com / admin123456")
    print("   User:  user@test.com / user123456")


if __name__ == "__main__":
    asyncio.run(reset_database_with_admin())
