# Supported DeepL Language Codes
SUPPORTED_LANGUAGES = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese",
}

CORE_TRANSLATION_LANGUAGES = ["EN", "DE", "FR", "ES", "IT"]

MAX_ROOM_MESSAGES = 100

# Message cleanup frequency (every N messages)
MESSAGE_CLEANUP_FREQUENCY = 10


# AI Entity Configuration
DEFAULT_AI_MODEL = "gpt-4o-mini"  # Cost optimization: 200x cheaper than gpt-4
DEFAULT_AI_TEMPERATURE = 0.7
DEFAULT_AI_MAX_TOKENS = 1024

# AI Entity Validation Limits
MIN_AI_TEMPERATURE = 0.0
MAX_AI_TEMPERATURE = 2.0
MIN_AI_MAX_TOKENS = 1
MAX_AI_MAX_TOKENS = 32000

# Note: Default system prompts are defined in app.core.ai_prompts
# Use get_prompt_template() to retrieve predefined prompt templates

# AI Provider Configuration
DEFAULT_PROVIDER_MODEL = "gpt-4o-mini"  # Cost optimization: 200x cheaper than gpt-4
DEFAULT_PROVIDER_TEMPERATURE = 0.7
DEFAULT_PROVIDER_MAX_TOKENS = 1024

# Context Management
MAX_CONTEXT_MESSAGES = 20  # Maximum messages to include in conversation context
MAX_MEMORY_ENTRIES = 10  # Maximum memory entries to retrieve per AI entity

# Authentication & Token Configuration
DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 7
DEFAULT_CSRF_TOKEN_LENGTH = 32

# Cookie Security Defaults
DEFAULT_COOKIE_SAMESITE = "lax"
DEFAULT_COOKIE_SECURE = False  # True in production via environment

# Time conversion constants
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
