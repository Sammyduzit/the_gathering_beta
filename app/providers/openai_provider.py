"""
OpenAI provider implementation using LangChain 0.3.x.

Provides chat completion functionality via OpenAI's API with modern async patterns.
"""

import logging
from typing import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.constants import (
    DEFAULT_PROVIDER_MAX_TOKENS,
    DEFAULT_PROVIDER_MODEL,
    DEFAULT_PROVIDER_TEMPERATURE,
)
from app.interfaces.ai_provider import AIProviderError, IAIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(IAIProvider):
    """OpenAI LLM provider implementation using LangChain."""

    def __init__(
        self,
        api_key: str,
        model_name: str = DEFAULT_PROVIDER_MODEL,
        default_temperature: float = DEFAULT_PROVIDER_TEMPERATURE,
        default_max_tokens: int = DEFAULT_PROVIDER_MAX_TOKENS,
    ):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model_name: Model to use (e.g., 'gpt-4', 'gpt-3.5-turbo')
            default_temperature: Default temperature for responses
            default_max_tokens: Default max tokens for responses
        """
        self.api_key = api_key
        self.model_name = model_name
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

        # Initialize LangChain ChatOpenAI
        self.llm = ChatOpenAI(
            api_key=api_key,
            model=model_name,
            temperature=default_temperature,
            max_tokens=default_max_tokens,
        )

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """
        Generate chat completion response from OpenAI.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system_prompt: Optional system prompt to prepend
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            Generated response text

        Raises:
            AIProviderError: If OpenAI API call fails
        """
        try:
            # Build LangChain message list
            lc_messages = []

            # Add system prompt if provided
            if system_prompt:
                lc_messages.append(SystemMessage(content=system_prompt))

            # Convert messages to LangChain format
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                else:  # user or assistant
                    lc_messages.append(HumanMessage(content=content))

            # Create LLM with overrides if provided
            llm = self.llm
            if temperature is not None or max_tokens is not None:
                llm = ChatOpenAI(
                    api_key=self.api_key,
                    model=self.model_name,
                    temperature=temperature if temperature is not None else self.default_temperature,
                    max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
                    **kwargs,
                )

            # Generate response
            response = await llm.ainvoke(lc_messages)
            return response.content

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise AIProviderError(f"Failed to generate response: {str(e)}", original_error=e)

    async def generate_streaming_response(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Generate streaming chat completion response from OpenAI.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system_prompt: Optional system prompt to prepend
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            **kwargs: Additional OpenAI-specific parameters

        Yields:
            Response chunks as they arrive

        Raises:
            AIProviderError: If OpenAI API call fails
        """
        try:
            # Build LangChain message list
            lc_messages = []

            # Add system prompt if provided
            if system_prompt:
                lc_messages.append(SystemMessage(content=system_prompt))

            # Convert messages to LangChain format
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))

            # Create LLM with overrides if provided
            llm = self.llm
            if temperature is not None or max_tokens is not None:
                llm = ChatOpenAI(
                    api_key=self.api_key,
                    model=self.model_name,
                    temperature=temperature if temperature is not None else self.default_temperature,
                    max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
                    streaming=True,
                    **kwargs,
                )

            # Stream response
            async for chunk in llm.astream(lc_messages):
                if hasattr(chunk, "content") and chunk.content:
                    yield chunk.content

        except Exception as e:
            logger.error(f"OpenAI streaming API call failed: {e}")
            raise AIProviderError(f"Failed to generate streaming response: {str(e)}", original_error=e)

    async def check_availability(self) -> bool:
        """
        Check if OpenAI provider is available and configured.

        Returns:
            True if provider is available, False otherwise
        """
        if not self.api_key:
            return False

        try:
            # Simple test call to verify API key
            test_messages = [HumanMessage(content="test")]
            await self.llm.ainvoke(test_messages)
            return True
        except Exception as e:
            logger.warning(f"OpenAI availability check failed: {e}")
            return False

    def get_model_name(self) -> str:
        """
        Get the current OpenAI model name.

        Returns:
            Model identifier (e.g., 'gpt-4')
        """
        return self.model_name
