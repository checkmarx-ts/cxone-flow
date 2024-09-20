from typing import Callable, Awaitable, List, Any, Dict
from requests import Response


async def async_api_page_generator(coro : Awaitable[Response], 
                                   data_extractor : Callable[[Response], List], kwargs_gen : Callable[[int], Dict]) -> Any:
    
    """_summary_

    A generator for paging API calls.

    Args:
        coro - an awaitable coroutine that will be called with kwargs provideded by kwargs_gen

        data_extractor - A callable that is given a response object returned by coro and is expected to
        returns a tuple containing elements:
            0: A list of elements that are provided in the generator.  None or an empty stops the generator.
            1: A boolean indicating this is the last page.

        kwargs_gen - A method that returns a list used as kwargs when executing coro.  A single int
        parameter is passed to indicate the current offset count.

    Yields:
        Any: An extracted object as returned by data_extractor callable.
    """
    offset = 0
    buf = []
    last_page = False

    while True:
        if len(buf) == 0 and not last_page:
            buf, last_page = data_extractor(await coro(**(kwargs_gen(offset))))
            
            if buf is None or len(buf) == 0:
                return
            offset = offset + 1
        elif len(buf) == 0 and last_page:
            return

        yield buf.pop()

