from markupsafe import escape
from typing import Annotated
from pydantic import AfterValidator


def sanitize_html_content(content: str | None) -> str | None:
    """
    Sanitize HTML content by
    :param content: Raw user input
    :return: Sanitized content
    """
    if content is None:
        return content
    return str(escape(content)).strip()


def sanitize_username(name: str) -> str:
    """
    Sanitize username
    :param name: Raw user input
    :return: Sanitized username
    """
    return str(escape(name)).strip()


def sanitize_room_text(text: str | None) -> str | None:
    """
    Sanitize room text fields (name, description)
    :param text: Raw text input for room infos
    :return: Sanitized text
    """
    if text is None:
        return text
    return str(escape(text)).strip()


SanitizedString = Annotated[str, AfterValidator(sanitize_html_content)]
SanitizedOptionalString = Annotated[str | None, AfterValidator(sanitize_html_content)]
SanitizedUsername = Annotated[str, AfterValidator(sanitize_username)]
SanitizedRoomText = Annotated[str | None, AfterValidator(sanitize_room_text)]
