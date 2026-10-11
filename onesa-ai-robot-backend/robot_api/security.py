"""Password verification and opaque session hashing; no control credentials in the UI."""

import asyncio
import getpass
import hashlib
import hmac
import secrets


def password_hash(password: str, salt: str | None = None) -> str:
    if not 12 <= len(password) <= 256:
        raise ValueError("Use a password of 12 to 256 characters")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return f"scrypt${salt}${digest.hex()}"


def verify(password: str, stored: str) -> bool:
    try:
        algorithm, salt, digest = stored.split("$")
        if algorithm != "scrypt":
            return False
        return hmac.compare_digest(password_hash(password, salt).split("$")[2], digest)
    except (ValueError, TypeError):
        return False


class VerificationBusy(RuntimeError):
    """Bound concurrent password hashing without queuing control requests."""


class PasswordVerifier:
    def __init__(self) -> None:
        self.slots = asyncio.Semaphore(2)

    async def verify(self, password: str, stored: str) -> bool:
        if self.slots.locked():
            raise VerificationBusy
        await self.slots.acquire()
        task = asyncio.create_task(asyncio.to_thread(verify, password, stored))

        def finished(completed: asyncio.Task) -> None:
            self.slots.release()
            # A disconnected caller must not free a slot while scrypt still runs,
            # or leave an unobserved exception in the background worker task.
            if not completed.cancelled():
                completed.exception()

        task.add_done_callback(finished)
        return await asyncio.shield(task)


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


if __name__ == "__main__":
    print(password_hash(getpass.getpass("Robot operator password: ")))
