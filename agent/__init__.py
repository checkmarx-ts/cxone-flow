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
        self.__opts_dict = opts_dict

    def _compile(self, opt_processor : Dict[str, Callable[[str], str]]=None) -> List[str]:
        ret_val = []

        for k in self.__opts_dict:

            value = self.__opts_dict[k]
            if opt_processor is None or k not in opt_processor.keys():
                proc = lambda x: x
            elif k in opt_processor.keys():
                proc = opt_processor[k]
            
            if len(k) == 0 or not self._validate_arg(k, value):
                self.log().warning(f"Command line option [{k}] is invalid, omitting.")
                continue
            
            if value is not None and not isinstance(value, str):
                continue

            if len(k) == 1:
                ret_val.append(f"-{k}")
            else:
                ret_val.append(f"--{k}")

            if value is not None:
                ret_val.append(proc(value))

        return ret_val

    def _validate_arg(self, arg_name : str, arg_value : str) -> bool:
        return True
    
    def has_one_of(self, arg_keys : List[str]) -> bool:
        return len([x for x in arg_keys if x in self.__opts_dict.keys()]) > 0

    def as_string(self, opt_processor : Dict[str, Callable[[str], str]]=None) -> str:
        return " ".join(self._compile(opt_processor))

    def as_args(self, opt_processor : Dict[str, Callable[[str], str]]=None) -> List[str]:
        return self._compile(opt_processor)
