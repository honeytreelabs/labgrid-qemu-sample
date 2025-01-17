import secrets
import string


def generate_random_string(k: int) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(k))
