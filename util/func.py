import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def wait_for(cond: Callable[[], T], desc: str, delay: float = 0.1, timeout: float = 10) -> T:
    """Wait for a condition to become true within a specified timeout.

    :param cond: A callable that returns a result with its boolean value representing the condition to wait for.
    :param desc: A description of the condition being waited for.
    :param delay: Time in seconds to wait between condition checks.
    :param timeout: Timeout in seconds to wait for the condition to become true.
    :return: True if the condition becomes true within the timeout.
    :raises TimeoutError: If the condition does not become true within the timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if (result := cond()) and bool(result):
            return result
        time.sleep(delay)  # Sleep briefly to avoid busy-waiting
    raise TimeoutError(f"Timeout while waiting for condition to become true: {desc}.")


S = TypeVar("S")


def retry_exc(func: Callable[[], S], exc_type: type[Exception], desc: str, delay: float = 1, timeout: float = 10) -> S:
    """Retry a function until it succeeds or a specific exception type is no longer raised.

    :param func: A callable to execute, which may raise the specified exception type.
    :param exc_type: The type of exception to handle during retries.
    :param desc: A description of the action being retried.
    :param delay: Time in seconds to wait between retries.
    :param timeout: Timeout in seconds to wait before giving up.
    :return: The result of the function if it succeeds.
    :raises TimeoutError: If the function does not succeed within the specified timeout.
    """
    start_time = time.time()
    exc: Exception | None = None
    while time.time() - start_time < timeout:
        try:
            return func()
        except exc_type as exc_:
            exc = exc_
            pass
        time.sleep(delay)  # Sleep briefly to avoid busy-waiting
    raise TimeoutError(f"Timeout while waiting for condition to become true: {desc}.") from exc
