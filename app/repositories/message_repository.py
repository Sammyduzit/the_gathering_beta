import logging
from abc import abstractmethod

from sqlalchemy import and_, desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageType
from app.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class IMessageRepository(BaseRepository[Message]):
    """Abstract interface for Message repository."""

    @abstractmethod
    async def create_room_message(
        self,
        room_id: int,
        content: str,
        sender_user_id: int | None = None,
        sender_ai_id: int | None = None,
        in_reply_to_message_id: int | None = None,
    ) -> Message:
        """Create a room-wide message (polymorphic sender)."""
        pass

    @abstractmethod
    async def create_conversation_message(
        self,
        conversation_id: int,
        content: str,
        sender_user_id: int | None = None,
        sender_ai_id: int | None = None,
        in_reply_to_message_id: int | None = None,
    ) -> Message:
        """Create a conversation message (polymorphic sender)."""
        pass

    @abstractmethod
    async def get_room_messages(self, room_id: int, page: int = 1, page_size: int = 50) -> tuple[list[Message], int]:
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
    async def get_latest_conversation_message(self, conversation_id: int) -> Message | None:
        """Get most recent message from a conversation."""
        pass

    @abstractmethod
    async def count_conversation_messages(self, conversation_id: int) -> int:
        """Count total messages in a conversation."""
        pass

    @abstractmethod
    async def get_recent_messages(
        self, room_id: int | None = None, conversation_id: int | None = None, limit: int = 10
    ) -> list[Message]:
        """
        Get recent messages from either a room or conversation.
        Unified method for fetching latest messages regardless of context.
        :param room_id: Room ID (exclusive with conversation_id)
        :param conversation_id: Conversation ID (exclusive with room_id)
        :param limit: Maximum number of messages to retrieve
        :return: List of recent messages ordered by sent_at descending (newest first)
        """
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
        self,
        room_id: int,
        content: str,
        sender_user_id: int | None = None,
        sender_ai_id: int | None = None,
        in_reply_to_message_id: int | None = None,
    ) -> Message:
        """Create a room-wide message (polymorphic sender)."""
        new_message = Message(
            sender_user_id=sender_user_id,
            sender_ai_id=sender_ai_id,
            content=content,
            message_type=MessageType.TEXT,
            room_id=room_id,
            conversation_id=None,
            in_reply_to_message_id=in_reply_to_message_id,
        )

        self.db.add(new_message)
        await self.db.commit()
        await self.db.refresh(new_message)

        attrs: list[str] = []
        if sender_user_id:
            attrs.append("sender_user")
        if sender_ai_id:
            attrs.append("sender_ai")

        if attrs:
            await self.db.refresh(new_message, attribute_names=attrs)

        return new_message

    async def create_conversation_message(
        self,
        conversation_id: int,
        content: str,
        sender_user_id: int | None = None,
        sender_ai_id: int | None = None,
        in_reply_to_message_id: int | None = None,
    ) -> Message:
        """Create a conversation message (polymorphic sender)."""
        new_message = Message(
            sender_user_id=sender_user_id,
            sender_ai_id=sender_ai_id,
            content=content,
            message_type=MessageType.TEXT,
            room_id=None,
            conversation_id=conversation_id,
            in_reply_to_message_id=in_reply_to_message_id,
        )

        self.db.add(new_message)
        await self.db.commit()
        await self.db.refresh(new_message)

        attrs: list[str] = []
        if sender_user_id:
            attrs.append("sender_user")
        if sender_ai_id:
            attrs.append("sender_ai")

        if attrs:
            await self.db.refresh(new_message, attribute_names=attrs)

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

        from sqlalchemy.orm import selectinload

        offset = (page - 1) * page_size
        messages_query = (
            select(Message)
            .options(selectinload(Message.sender_user), selectinload(Message.sender_ai))
            .where(and_(Message.room_id == room_id, Message.conversation_id.is_(None)))
            .order_by(desc(Message.sent_at))
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(messages_query)
        messages = list(result.scalars().all())

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
        from sqlalchemy.orm import selectinload

        messages_query = (
            select(Message)
            .options(selectinload(Message.sender_user), selectinload(Message.sender_ai))
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
        messages = list(result.scalars().all())

        return messages, total_count

    async def get_user_messages(self, user_id: int, limit: int = 50) -> list[Message]:
        """Get messages sent by a specific user."""
        from sqlalchemy.orm import selectinload

        query = (
            select(Message)
            .options(selectinload(Message.sender_user), selectinload(Message.sender_ai))
            .where(Message.sender_user_id == user_id)
            .order_by(desc(Message.sent_at))
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_room_messages(self, room_id: int, limit: int = 10) -> list[Message]:
        """Get latest messages from a room."""
        from sqlalchemy.orm import selectinload

        query = (
            select(Message)
            .options(selectinload(Message.sender_user), selectinload(Message.sender_ai))
            .where(and_(Message.room_id == room_id, Message.conversation_id.is_(None)))
            .order_by(desc(Message.sent_at))
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_conversation_message(self, conversation_id: int) -> Message | None:
        """Get most recent message from a conversation."""
        from sqlalchemy.orm import selectinload

        query = (
            select(Message)
            .options(selectinload(Message.sender_user), selectinload(Message.sender_ai))
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.sent_at))
            .limit(1)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def count_conversation_messages(self, conversation_id: int) -> int:
        """Count total messages in a conversation."""
        query = select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        result = await self.db.execute(query)
        return result.scalar_one() or 0

    async def get_recent_messages(
        self, room_id: int | None = None, conversation_id: int | None = None, limit: int = 10
    ) -> list[Message]:
        """
        Get recent messages from either a room or conversation.
        Unified method for fetching latest messages regardless of context.
        """
        from sqlalchemy.orm import selectinload

        # Validate XOR: exactly one must be set
        if (room_id is None) == (conversation_id is None):
            raise ValueError("Exactly one of room_id or conversation_id must be provided")

        # Build query based on context
        query = select(Message).options(selectinload(Message.sender_user), selectinload(Message.sender_ai))

        if room_id:
            # Room messages (exclude conversation messages in the room)
            query = query.where(and_(Message.room_id == room_id, Message.conversation_id.is_(None)))
        else:
            # Conversation messages
            query = query.where(Message.conversation_id == conversation_id)

        query = query.order_by(desc(Message.sent_at)).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Message]:
        """Get all messages with pagination."""
        query = select(Message).limit(limit).offset(offset).order_by(desc(Message.sent_at))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def cleanup_old_room_messages(self, room_id: int, keep_count: int = 100) -> int:
        """Delete old room messages, keeping only the most recent ones"""
        try:
            threshold_query = (
                select(Message.sent_at)
                .where(and_(Message.room_id == room_id, Message.conversation_id.is_(None)))
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
