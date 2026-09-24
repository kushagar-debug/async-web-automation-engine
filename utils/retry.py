"""
Asynchronous Retry Policy and Fault-Tolerance Utilities.

Implements exponential backoff with full jitter to prevent thundering herd
scenarios during network hiccups, transient gateway timeouts, and DOM reflow stalls.
"""

from __future__ import annotations

import asyncio
import functools
import random
from typing import Any, Callable, Coroutine, Tuple, Type, TypeVar

from .logger import get_logger

logger = get_logger("engine.retry")

T = TypeVar("T")


def async_exponential_backoff(
    retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., Coroutine[Any, Any, T]]], Callable[..., Coroutine[Any, Any, T]]]:
    """
    Decorator that transparently retries an async coroutine with exponential backoff and jitter.

    :param retries: Total number of retry attempts before propagating exception.
    :param initial_delay: Delay in seconds before first retry.
    :param backoff_factor: Multiplier applied per failure iteration.
    :param jitter: Adds randomized noise to the delay to distribute concurrent retries.
    :param exceptions: Tuple of catchable exception classes.
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            current_delay = initial_delay

            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    attempt += 1
                    if attempt > retries:
                        logger.error(
                            f"Operation '{func.__name__}' failed after {retries} retries: {exc}"
                        )
                        raise

                    sleep_time = current_delay
                    if jitter:
                        sleep_time = random.uniform(0.5 * current_delay, 1.5 * current_delay)

                    logger.warning(
                        f"Retryable failure in '{func.__name__}' (attempt {attempt}/{retries}): {exc}. "
                        f"Backing off for {sleep_time:.2f}s..."
                    )
                    await asyncio.sleep(sleep_time)
                    current_delay *= backoff_factor

        return wrapper

    return decorator
