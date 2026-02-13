import asyncio
import functools
import logging

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, backoff_factor: float = 2.0):
    """
    Decorator for async functions with exponential backoff retry.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries in seconds.
        backoff_factor: Multiplier for delay after each retry.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (backoff_factor ** (attempt - 1))
                        logger.warning(
                            f"Attempt {attempt}/{max_retries} failed for '{func.__name__}': {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for '{func.__name__}': {e}"
                        )
            raise last_exception
        return wrapper
    return decorator


async def retry_async(coro_func, *args, max_retries: int = 3, base_delay: float = 1.0,
                      backoff_factor: float = 2.0, **kwargs):
    """
    Retry an async callable with exponential backoff (non-decorator version).

    Args:
        coro_func: Async callable to retry.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries in seconds.
        backoff_factor: Multiplier for delay after each retry.
    """
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = base_delay * (backoff_factor ** (attempt - 1))
                logger.warning(
                    f"Attempt {attempt}/{max_retries} failed: {e}. Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries} attempts failed: {e}")
    raise last_exception
