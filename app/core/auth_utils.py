from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"])


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    :param password: Plain text password
    :return: Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against hash.
    :param plain_password: Plain text password
    :param hashed_password: Hashed password
    :return: True if password matches, else False.
    """
    return pwd_context.verify(plain_password, hashed_password)
