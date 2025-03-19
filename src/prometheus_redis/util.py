import time
import logging
from typing import Callable
from functools import wraps


logger = logging.getLogger(__name__)


def timer(metric_callback: Callable, **labels):
    def wrapper(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            metric_callback(time.time() - start, labels=labels)
            return result
        return func_wrapper
    return wrapper


def log_exceptions(func):
    """Wrap function for process any Exception and write it to log."""
    @wraps(func)
    async def silent_function(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception:
            logger.exception("Error while send metric to Redis. Function %s", func)

    return silent_function
