"""
Service interfaces for dependency injection.

This module defines abstract interfaces for all external dependencies
and services, enabling clean dependency injection and easy testing.
"""

from .translator import TranslatorInterface

__all__ = [
    "TranslatorInterface",
]