import asyncio, aio_pika, os
from typing import Any, Callable, Awaitable


async def mq_agent(coro : Callable[[aio_pika.abc.AbstractIncomingMessage], Awaitable[Any]],  mq_client : aio_pika.abc.AbstractRobustConnection, moniker : str, 
                queue : str, prefetch : int=2):

    async with mq_client.channel() as channel:
        await channel.set_qos(prefetch_count=prefetch)
        q = await channel.get_queue(queue)

        await q.consume(coro, arguments = {
            "moniker" : moniker}, consumer_tag = f"{coro.__name__}.{moniker}.{os.getpid()}")

        while True:
            await asyncio.Future()
