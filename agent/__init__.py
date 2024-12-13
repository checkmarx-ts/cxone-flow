import asyncio, aio_pika, os, logging
from typing import Any, Callable, Awaitable, Dict, List


async def mq_agent(
    coro: Callable[[aio_pika.abc.AbstractIncomingMessage], Awaitable[Any]],
    mq_client: aio_pika.abc.AbstractRobustConnection,
    moniker: str,
    queue: str,
    prefetch: int = 2,
):

    async with mq_client.channel() as channel:
        await channel.set_qos(prefetch_count=prefetch)
        q = await channel.get_queue(queue)

        if hasattr(coro, "__name__"):
            name = coro.__name__
        elif hasattr(coro, "__class__"):
            name = coro.__class__.__name__
        else:
            name = "unknown"

        await q.consume(
            coro,
            arguments={"moniker": moniker},
            consumer_tag=f"{name}.{moniker}.{os.getpid()}",
        )

        while True:
            await asyncio.Future()


class DictCmdLineOpts:
    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)

    def __init__(self, opts_dict: Dict[str, str]):
        self.__args_list = []

        for k in opts_dict:

            value = opts_dict[k]
            
            if len(k) == 0 or not self._validate_arg(k, value):
                self.log().warning(f"Command line option [{k}] is invalid, omitting.")
                continue
            
            if value is not None and not isinstance(value, str):
                continue

            if len(k) == 1:
                self.__args_list.append(f"-{k}")
            else:
                self.__args_list.append(f"--{k}")

            if value is not None:
                self.__args_list.append(value)

    def _validate_arg(self, arg_name : str, arg_value : str) -> bool:
        return True

    def as_string(self) -> str:
        return " ".join(self.__args_list)

    def as_args(self) -> List[str]:
        return self.__args_list
