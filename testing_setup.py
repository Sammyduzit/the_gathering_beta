from app.models.user import User
from app.models.room import Room
from app.core.auth_utils import hash_password
from app.core.database import SessionLocal
from app.services.avatar_service import generate_avatar_url
from sqlalchemy import select


def create_test_users():
    """Create test admin and user"""
    with SessionLocal() as db:
        try:
            test_users = [
                {
                    "email": "testadmin@thegathering.com",
                    "username": "Testadmin",
                    "password": "adminpass",
                    "is_admin": True,
                },
                {
                    "email": "alice@test.com",
                    "username": "Alice",
                    "password": "alice123",
                    "is_admin": False,
                },
                {
                    "email": "bob@test.com",
                    "username": "Bob",
                    "password": "bob12345",
                    "is_admin": False,
                },
                {
                    "email": "carol@test.com",
                    "username": "Carol",
                    "password": "carol123",
                    "is_admin": False,
                },
                {
                    "email": "dave@test.com",
                    "username": "Dave",
                    "password": "dave1234",
                    "is_admin": False,
                },
            ]
            created_users = []
            for user_data in test_users:
                user_query = select(User).where(User.email == user_data["email"])
                result = db.execute(user_query)
                existing_user = result.scalar_one_or_none()

                if not existing_user:
                    new_user = User(
                        email=user_data["email"],
                        username=user_data["username"],
                        password_hash=hash_password(user_data["password"]),
                        avatar_url=generate_avatar_url(user_data["username"]),
                        is_admin=user_data["is_admin"],
                    )
                    db.add(new_user)
                    created_users.append(user_data)

            if created_users:
                db.commit()

        except Exception as e:
            print(f"Error creating users: {e}")
            db.rollback()
            raise

    return created_users


def create_test_rooms():
    """Create test rooms for tests"""
    with SessionLocal() as db:
        try:
            test_rooms = [
                {
                    "name": "Lobby",
                    "description": "Main lobby - everyone welcome",
                    "max_users": 50,
                    "is_translation_enabled": False,
                },
                {
                    "name": "Gaming",
                    "description": "Gaming discussion and planning",
                    "max_users": 20,
                    "is_translation_enabled": False,
                },
                {
                    "name": "Work",
                    "description": "Work-related discussions",
                    "max_users": 15,
                    "is_translation_enabled": False,
                },
                {
                    "name": "Coffee Chat",
                    "description": "Casual conversations",
                    "max_users": 10,
                    "is_translation_enabled": False,
                },
                {
                    "name": "TranslationTest",
                    "description": "Testing Translation Service",
                    "max_users": 10,
                    "is_translation_enabled": True,
                },
            ]

            created_rooms = []
            for room_data in test_rooms:
                room_query = select(Room).where(Room.name == room_data["name"])
                result = db.execute(room_query)
                existing_room = result.scalar_one_or_none()

                if not existing_room:
                    new_room = Room(
                        name=room_data["name"],
                        description=room_data["description"],
                        max_users=room_data["max_users"],
                        is_translation_enabled=room_data["is_translation_enabled"],
                    )
                    db.add(new_room)
                    created_rooms.append(room_data)

            if created_rooms:
                db.commit()

        except Exception as e:
            print(f"Error creating rooms: {e}")
            db.rollback()
            raise

    return created_rooms


def setup_complete_test_environment():
    """Create complete test environment for development"""
    print("\nCreating test environment...\n")

    created_users = create_test_users()
    created_rooms = create_test_rooms()

    if created_users:
        print("═" * 68)
        print(" " * 25 + "TEST USERS")
        print()
        for user in created_users:
            user_type = "ADMIN " if user["is_admin"] else "USER  "
            email = user["email"]
            password = user["password"]
            line = f"  {user_type}: {email:<35} | pw: {password:<10}"
            print(line)

    if created_rooms:
        if created_users:
            print()
        print(" " * 25 + "TEST ROOMS")
        print()
        for room in created_rooms:
            name = room["name"]
            description = (
                room["description"][:40] + "..."
                if len(room["description"]) > 40
                else room["description"]
            )
            line = f"  ROOM : {name:<20} | {description:<35}"
            print(line)

    print("═" * 68)

    print("TEST ENVIRONMENT READY!")
