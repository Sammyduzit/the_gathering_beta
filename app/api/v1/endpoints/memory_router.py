"""
Memory API endpoints for AI memory management.

Provides CRUD operations and search functionality for AI memories.
Admin-only access for security and privacy.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth_dependencies import get_current_admin_user
from app.core.csrf_dependencies import validate_csrf
from app.models.ai_memory import AIMemory
from app.models.user import User
from app.repositories.ai_memory_repository import IAIMemoryRepository
from app.repositories.repository_dependencies import get_ai_memory_repository
from app.schemas.memory_schemas import (
    MemoryCreate,
    MemoryListResponse,
    MemoryResponse,
    MemoryUpdate,
    PersonalityUploadRequest,
    PersonalityUploadResponse,
)
from app.services.personality_memory_service import PersonalityMemoryService
from app.services.service_dependencies import get_personality_memory_service
from app.services.yake_extractor import YakeKeywordExtractor

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=MemoryListResponse)
async def get_memories(
    entity_id: int | None = Query(None, description="Filter by AI entity ID"),
    conversation_id: int | None = Query(None, description="Filter by conversation ID"),
    room_id: int | None = Query(None, description="Filter by room ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    current_admin: User = Depends(get_current_admin_user),
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
) -> MemoryListResponse:
    """
    Get AI memories with pagination and filtering (Admin only).

    Args:
        entity_id: Optional AI entity ID filter
        conversation_id: Optional conversation ID filter
        room_id: Optional room ID filter
        page: Page number (starts at 1)
        page_size: Items per page (max 100)
        current_admin: Current authenticated admin
        memory_repo: Memory repository instance

    Returns:
        Paginated list of memories
    """
    # Calculate offset
    offset = (page - 1) * page_size

    # Get memories based on filters
    if entity_id:
        memories = await memory_repo.get_entity_memories(
            entity_id=entity_id,
            room_id=room_id,
            limit=page_size,
        )
        # For entity-specific queries, we don't have total count easily
        # This is a simplified approach - in production, add count query
        total = len(memories)
    else:
        # Get all memories with pagination
        memories = await memory_repo.get_all(limit=page_size, offset=offset)
        # Simplified total count
        total = len(memories) + offset

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return MemoryListResponse(
        memories=memories,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory_by_id(
    memory_id: int,
    current_admin: User = Depends(get_current_admin_user),
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
) -> MemoryResponse:
    """
    Get single memory by ID (Admin only).

    Args:
        memory_id: Memory ID
        current_admin: Current authenticated admin
        memory_repo: Memory repository instance

    Returns:
        Memory details

    Raises:
        HTTPException: 404 if memory not found
    """
    memory = await memory_repo.get_by_id(memory_id)
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Memory {memory_id} not found")

    return memory


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    memory_data: MemoryCreate,
    current_admin: User = Depends(get_current_admin_user),
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
    _csrf: None = Depends(validate_csrf),
) -> MemoryResponse:
    """
    Create new AI memory manually (Admin only).

    Keywords are automatically extracted from summary if not provided.

    Args:
        memory_data: Memory creation data
        current_admin: Current authenticated admin
        memory_repo: Memory repository instance

    Returns:
        Created memory

    Raises:
        HTTPException: 400 if validation fails
    """
    # Validate XOR constraint: either conversation_id OR room_id, not both
    if memory_data.conversation_id and memory_data.room_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot specify both conversation_id and room_id",
        )

    if not memory_data.conversation_id and not memory_data.room_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify either conversation_id or room_id",
        )

    # Auto-extract keywords if not provided
    keywords = memory_data.keywords
    if not keywords:
        extractor = YakeKeywordExtractor()
        keywords = await extractor.extract_keywords(memory_data.summary, max_keywords=10)

    # Build metadata
    memory_metadata = {
        "created_by": "admin",
        "extractor_used": "yake" if not memory_data.keywords else "manual",
        "version": 1,
    }

    # Create memory
    memory = AIMemory(
        entity_id=memory_data.entity_id,
        conversation_id=memory_data.conversation_id,
        room_id=memory_data.room_id,
        summary=memory_data.summary,
        memory_content=memory_data.memory_content,
        keywords=keywords,
        importance_score=memory_data.importance_score,
        memory_metadata=memory_metadata,
    )

    created_memory = await memory_repo.create(memory)
    return created_memory


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: int,
    memory_data: MemoryUpdate,
    current_admin: User = Depends(get_current_admin_user),
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
    _csrf: None = Depends(validate_csrf),
) -> MemoryResponse:
    """
    Update existing AI memory (Admin only).

    Keywords are re-extracted if summary changes.

    Args:
        memory_id: Memory ID to update
        memory_data: Memory update data (partial)
        current_admin: Current authenticated admin
        memory_repo: Memory repository instance

    Returns:
        Updated memory

    Raises:
        HTTPException: 404 if memory not found
    """
    # Get existing memory
    memory = await memory_repo.get_by_id(memory_id)
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Memory {memory_id} not found")

    # Track if summary changed for keyword re-extraction
    summary_changed = False

    # Update fields if provided
    if memory_data.summary is not None:
        summary_changed = memory.summary != memory_data.summary
        memory.summary = memory_data.summary

    if memory_data.memory_content is not None:
        memory.memory_content = memory_data.memory_content

    if memory_data.importance_score is not None:
        memory.importance_score = memory_data.importance_score

    # Re-extract keywords if summary changed or explicitly provided
    if memory_data.keywords is not None:
        memory.keywords = memory_data.keywords
        # Update metadata
        if memory.memory_metadata:
            memory.memory_metadata["extractor_used"] = "manual"
    elif summary_changed:
        extractor = YakeKeywordExtractor()
        memory.keywords = await extractor.extract_keywords(memory.summary, max_keywords=10)
        # Update metadata
        if memory.memory_metadata:
            memory.memory_metadata["extractor_used"] = "yake"

    # Update version in metadata
    if memory.memory_metadata:
        memory.memory_metadata["version"] = memory.memory_metadata.get("version", 1) + 1

    updated_memory = await memory_repo.update(memory)
    return updated_memory


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: int,
    current_admin: User = Depends(get_current_admin_user),
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
    _csrf: None = Depends(validate_csrf),
) -> None:
    """
    Delete AI memory (Admin only).

    Hard delete - memory is permanently removed.

    Args:
        memory_id: Memory ID to delete
        current_admin: Current authenticated admin
        memory_repo: Memory repository instance

    Raises:
        HTTPException: 404 if memory not found
    """
    deleted = await memory_repo.delete(memory_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Memory {memory_id} not found")


@router.get("/search", response_model=list[MemoryResponse])
async def search_memories(
    entity_id: int = Query(..., description="AI entity ID to search"),
    keywords: str = Query(..., description="Comma-separated keywords"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    current_admin: User = Depends(get_current_admin_user),
    memory_repo: IAIMemoryRepository = Depends(get_ai_memory_repository),
) -> list[MemoryResponse]:
    """
    Search AI memories by keywords (Admin only).

    Args:
        entity_id: AI entity ID to search
        keywords: Comma-separated keywords (e.g., "python,fastapi")
        limit: Maximum number of results (max 50)
        current_admin: Current authenticated admin
        memory_repo: Memory repository instance

    Returns:
        List of matching memories ordered by importance
    """
    # Parse keywords
    keyword_list = [kw.strip().lower() for kw in keywords.split(",") if kw.strip()]

    if not keyword_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one keyword required",
        )

    # Search memories
    memories = await memory_repo.search_by_keywords(
        entity_id=entity_id,
        keywords=keyword_list,
        limit=limit,
    )

    return memories


@router.post(
    "/admin/ai-entities/{entity_id}/personality",
    response_model=PersonalityUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_personality(
    entity_id: int,
    request: PersonalityUploadRequest,
    current_admin: User = Depends(get_current_admin_user),
    personality_service: PersonalityMemoryService = Depends(get_personality_memory_service),
    _csrf: None = Depends(validate_csrf),
) -> PersonalityUploadResponse:
    """
    Upload personality knowledge base for AI entity (Admin only).

    Creates global personality memories (not user-specific).
    Text is chunked and embedded for semantic search.

    Args:
        entity_id: AI entity ID
        request: Upload request with text, category, and metadata
        current_admin: Current authenticated admin
        personality_service: Personality memory service instance

    Returns:
        Upload result with memory count and IDs

    Raises:
        HTTPException: 400 if upload fails
    """
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text content cannot be empty",
        )

    try:
        memories = await personality_service.upload_personality(
            entity_id=entity_id,
            text=request.text,
            category=request.category,
            metadata=request.metadata or {},
        )

        return PersonalityUploadResponse(
            created_memories=len(memories),
            memory_ids=[m.id for m in memories],
            category=request.category,
            chunks=len(memories),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Personality upload failed: {str(e)}",
        )
