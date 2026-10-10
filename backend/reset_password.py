"""
Sets a user's password from the command line: the fallback when email isn't
configured (or the reset email went missing).

    docker compose exec backend python reset_password.py someone@example.com

Prompts twice for the new password without echoing it. Must run from
backend/ (flat imports), which is the container's working directory.
"""
import argparse
import getpass
import sys

from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from auth import get_password_hash
from schemas import PASSWORD_MIN_LENGTH


def set_password(db: Session, email: str, new_password: str) -> bool:
    """
    Sets the password of the account with this email (case-insensitive) and
    retires its outstanding reset links. Returns False if there is no such
    account. Commits.
    """
    if len(new_password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    user = (
        db.query(models.DimUser)
        .filter(func.lower(models.DimUser.email) == email.strip().lower())
        .first()
    )
    if user is None:
        return False
    user.hashed_password = get_password_hash(new_password)
    Token = models.PasswordResetToken
    db.query(Token).filter(Token.user_id == user.user_id, Token.used_at.is_(None)).update(
        {Token.used_at: func.now()}, synchronize_session=False
    )
    db.commit()
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Set a user's password.")
    parser.add_argument("email")
    args = parser.parse_args(argv)

    new_password = getpass.getpass("New password: ")
    if new_password != getpass.getpass("Repeat it: "):
        print("Passwords don't match; nothing changed.", file=sys.stderr)
        return 1

    from database import SessionLocal
    with SessionLocal() as db:
        try:
            found = set_password(db, args.email, new_password)
        except ValueError as e:
            print(f"{e} Nothing changed.", file=sys.stderr)
            return 1
    if not found:
        print(f"No account with email {args.email!r}; nothing changed.", file=sys.stderr)
        return 1
    print(f"Password updated for {args.email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
