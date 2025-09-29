import logging
from abc import abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.exc import SQLAlchemyError

from app.models.message import Message, MessageType
from app.models.user import User
from app.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class IMessageRepository(BaseRepository[Message]):
    """Abstract interface for Message repository."""

    @abstractmethod
    async def create_room_message(
        self, sender_id: int, room_id: int, content: str
    ) -> Message:
        """Create a room-wide message."""
        pass

    @abstractmethod
    async def create_conversation_message(
        self, sender_id: int, conversation_id: int, content: str
    ) -> Message:
        """Create a conversation message (private/group)."""
        pass

    @abstractmethod
    async def get_room_messages(
        self, room_id: int, page: int = 1, page_size: int = 50
    ) -> tuple[list[Message], int]:
        """Get room messages with pagination."""
        pass

    @abstractmethod
    async def get_conversation_messages(
        self,
        conversation_id: int,
        page: int = 1,
        page_size: int = 50,
        user_language: str | None = None,
    ) -> tuple[list[Message], int]:
        """Get conversation messages with pagination."""
        pass

    @abstractmethod
    async def get_user_messages(self, user_id: int, limit: int = 50) -> list[Message]:
        """Get messages sent by a specific user."""
        pass

    @abstractmethod
    async def get_latest_room_messages(self, room_id: int, limit: int = 10) -> list[Message]:
        """Get latest messages from a room."""
        pass

    @abstractmethod
    async def cleanup_old_room_messages(self, room_id: int, keep_count: int = 100) -> int:
        """Delete old room messages, keeping only the most recent ones"""
        pass


class MessageRepository(IMessageRepository):
    """SQLAlchemy implementation of Message repository."""

    def __init__(self, db: AsyncSession):
        """
        Initialize with async database session.
        :param db: SQLAlchemy async database session
        """
        super().__init__(db)

    async def get_by_id(self, id: int) -> Message | None:
        """Get message by ID."""
        query = select(Message).where(Message.id == id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_room_message(
        self, sender_id: int, room_id: int, content: str
    ) -> Message:
        """Create a room-wide message."""
        new_message = Message(
            sender_id=sender_id,
            content=content,
            message_type=MessageType.TEXT,
            room_id=room_id,
            conversation_id=None,
        )

        self.db.add(new_message)
        await self.db.commit()
        await self.db.refresh(new_message)
        return new_message

    async def create_conversation_message(
        self, sender_id: int, conversation_id: int, content: str
    ) -> Message:
        """Create a conversation message (private/group)."""
        new_message = Message(
            sender_id=sender_id,
            content=content,
            message_type=MessageType.TEXT,
            room_id=None,
            conversation_id=conversation_id,
        )

        self.db.add(new_message)
        await self.db.commit()
        await self.db.refresh(new_message)
        return new_message

    async def get_room_messages(
        self,
        room_id: int,
        page: int = 1,
        page_size: int = 50,
        user_language: str | None = None,
    ) -> tuple[list[Message], int]:
        """Get room messages with pagination."""
        count_query = select(func.count(Message.id)).where(
            and_(Message.room_id == room_id, Message.conversation_id.is_(None))
        )
        result = await self.db.execute(count_query)
        total_count = result.scalar() or 0

        offset = (page - 1) * page_size
        messages_query = (
            select(Message, User.username)
            .join(User, Message.sender_id == User.id)
            .where(and_(Message.room_id == room_id, Message.conversation_id.is_(None)))
            .order_by(desc(Message.sent_at))
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(messages_query)
        message_rows = result.all()

        # Add sender_username to message objects
        messages = []
        for message_object, username in message_rows:
            message_object.sender_username = username
            messages.append(message_object)

        return messages, total_count

    async def get_conversation_messages(
        self,
        conversation_id: int,
        page: int = 1,
        page_size: int = 50,
        user_language: str | None = None,
    ) -> tuple[list[Message], int]:
        """Get conversation messages with pagination."""
        count_query = select(func.count(Message.id)).where(
            and_(Message.conversation_id == conversation_id, Message.room_id.is_(None))
        )
        result = await self.db.execute(count_query)
        total_count = result.scalar() or 0

        offset = (page - 1) * page_size
        messages_query = (
            select(Message, User.username)
            .join(User, Message.sender_id == User.id)
            .where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.room_id.is_(None),
                )
            )
            .order_by(desc(Message.sent_at))
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(messages_query)
        message_rows = result.all()

        # Add sender_username to message objects
        messages = []
        for message_object, username in message_rows:
            message_object.sender_username = username
            messages.append(message_object)

        return messages, total_count

    async def get_user_messages(self, user_id: int, limit: int = 50) -> list[Message]:
        """Get messages sent by a specific user."""
        query = (
            select(Message)
            .where(Message.sender_id == user_id)
            .order_by(desc(Message.sent_at))
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_room_messages(self, room_id: int, limit: int = 10) -> list[Message]:
        """Get latest messages from a room."""
        query = (
            select(Message, User.username)
            .join(User, Message.sender_id == User.id)
            .where(and_(Message.room_id == room_id, Message.conversation_id.is_(None)))
            .order_by(desc(Message.sent_at))
            .limit(limit)
        )

        result = await self.db.execute(query)
        message_rows = result.all()

        # Add sender_username to message objects
        messages = []
        for message_object, username in message_rows:
            message_object.sender_username = username
            messages.append(message_object)

        return messages

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Message]:
        """Get all messages with pagination."""
        query = (
            select(Message).limit(limit).offset(offset).order_by(desc(Message.sent_at))
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def cleanup_old_room_messages(self, room_id: int, keep_count: int = 100) -> int:
        """Delete old room messages, keeping only the most recent ones"""
        try:
            threshold_query = (
                select(Message.sent_at)
                .where(
                    and_(Message.room_id == room_id, Message.conversation_id.is_(None))
                )
                .order_by(Message.sent_at.desc())
                .offset(keep_count - 1)
                .limit(1)
            )

            result = await self.db.execute(threshold_query)
            threshold_result = result.scalar_one_or_none()

            if not threshold_result:
                return 0

            old_messages_query = select(Message.id).where(
                and_(
                    Message.room_id == room_id,
                    Message.conversation_id.is_(None),
                    Message.sent_at < threshold_result,
                )
            )

            result = await self.db.execute(old_messages_query)
            old_messages = result.all()

            deleted_count = 0
            for message in old_messages:
                self.db.delete(message)
                deleted_count += 1

            await self.db.commit()

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old messages from room {room_id}")

            return deleted_count

        except SQLAlchemyError as e:
            logger.error(f"Error cleaning up room messages: {e}")
            await self.db.rollback()
            return 0

    async def create(self, message: Message) -> Message:
        """Create new message."""
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def update(self, message: Message) -> Message:
        """Update existing message."""
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def delete(self, id: int) -> bool:
        """Delete message by ID."""
        message = await self.get_by_id(id)
        if message:
            await self.db.delete(message)
            await self.db.commit()
            return True
        return False

    async def exists(self, id: int) -> bool:
        """Check if message exists by ID."""
        message = await self.get_by_id(id)
        return message is not None
