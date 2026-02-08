import bcrypt
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from typing import Optional
import os

# 1. Setup password hashing


# 2. Configuration (come from .env when in prod)
SECRET_KEY= os.getenv("SECRET_KEY", "super_secret_key_for_dev_only_change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password, hashed_password):
    """
    Checks if the password typed by the user matches the hash in the DB.
    
    :param plain_password: Plain password
    :param hashed_password: Hashed password as output
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except ValueError:
        # Prevents crashing if the hash is in ivalid/empty
        return False
    
def get_password_hash(password: str) -> str:
    """
    Takes a plain password and scrambles it

    :param password: user password
    """
    
    # Convert strings to bytes
    pwd_bytes = password.encode("utf-8")

    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed =bcrypt.hashpw(pwd_bytes, salt)

    # Return as string so as it gan be stored in postgres as text
    return hashed.decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Generates the JWT "passport" string.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


