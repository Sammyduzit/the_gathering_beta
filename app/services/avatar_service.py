import urllib.parse
import requests
import random


def get_available_avatar_styles() -> list[str]:
    """
    Get list of available DiceBear avatar styles from API
    with fallback of hardcoded list.
    :return: List of available styles.
    """
    try:
        response = requests.get("https://api.dicebear.com/7.x/styles", timeout=5)

        if response.status_code == 200:
            styles_data = response.json()
            return [style["id"] for style in styles_data if "id" in style]

    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"Could not fetch DiceBear styles from API : {e}")
        print("Fallback to hardcoded style list")

    return [
        "bottts",
        "avataaars",
        "big-smile",
        "identicon",
        "initials",
        "pixel-art",
        "adventurer",
        "big-ears",
        "croodles",
        "fun-emoji",
        "lorelei",
        "micah",
        "miniavs",
        "open-peeps",
        "personas",
        "rings",
        "shapes",
    ]


def get_random_avatar_style() -> str:
    """
    Get a random avatar style from available styles.
    :return: Random style name
    """
    styles = get_available_avatar_styles()
    return random.choice(styles)


def is_valid_avatar_style(style: str) -> bool:
    """
    Check if style is valid/available.
    :param style: Style to validate
    :return: True if available, else False
    """
    available_styles = get_available_avatar_styles()
    return style.lower() in [
        available_style.lower() for available_style in available_styles
    ]


def generate_avatar_url(username: str, style: str = "bottts") -> str:
    """
    Generate DiceBear avatar URL based on username.
    :param username: Username used for avatar
    :param style: DiceBear style (default: Bottts)
    :return: Avatar URL
    """
    if not is_valid_avatar_style(style):
        print(f"Warning: Invalid style '{style}', falling back to 'bottts'")
        style = "bottts"

    safe_username = urllib.parse.quote_plus(username.lower())

    avatar_url = f"https://api.dicebear.com/7.x/{style}/svg?seed={safe_username}"

    return avatar_url
