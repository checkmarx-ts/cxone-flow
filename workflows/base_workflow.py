import logging, pamqp.base, pamqp.commands, aio_pika


class AbstractAsyncWorkflow:

    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)


    @staticmethod
    def _log_publish_result(result : pamqp.base.Frame, log_msg : str):
        if type(result) == pamqp.commands.Basic.Ack:
            AbstractAsyncWorkflow.log().debug(f"Started {log_msg}")
        else:
            AbstractAsyncWorkflow.log().error(f"Unable to start {log_msg}")


    async def _publish(self, mq_client : aio_pika.abc.AbstractRobustConnection, topic : str, msg : aio_pika.abc.AbstractMessage, log_msg : str, exchange : str):
        async with await mq_client.channel() as channel:
            exchange = await channel.get_exchange(exchange)

            if exchange:
                AbstractAsyncWorkflow._log_publish_result(await exchange.publish(msg, routing_key = topic), log_msg)
            else:
                AbstractAsyncWorkflow.log().error(f"Client [{mq_client}] unable to retrieve exchange [{exchange}]")

