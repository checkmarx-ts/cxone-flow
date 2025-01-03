import logging, pamqp.base, pamqp.commands, aio_pika


class AbstractAsyncWorkflow:

    @classmethod
    def log(clazz):
        return logging.getLogger(clazz.__name__)


    @staticmethod
    def _log_publish_result(result : pamqp.base.Frame, log_msg : str) -> bool:
        if type(result) == pamqp.commands.Basic.Ack:
            AbstractAsyncWorkflow.log().debug(f"Published {log_msg}")
            return True
        else:
            AbstractAsyncWorkflow.log().error(f"Unable to publish {log_msg}")
            return False


    async def _publish(self, mq_client : aio_pika.abc.AbstractRobustConnection, topic : str, 
                       msg : aio_pika.abc.AbstractMessage, log_msg : str, exchange : str) -> bool:
        try:
            channel = await mq_client.channel()
            exchange = await channel.get_exchange(exchange)

            if exchange:
                return AbstractAsyncWorkflow._log_publish_result(await exchange.publish(msg, routing_key = topic), log_msg)
            else:
                AbstractAsyncWorkflow.log().error(f"Client [{mq_client}] unable to retrieve exchange [{exchange}]")
            
            return False
        except Exception:
            raise
        finally:
            await channel.close()


