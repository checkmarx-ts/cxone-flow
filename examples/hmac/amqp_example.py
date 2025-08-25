import hmac
import asyncio, aio_pika

# An example of how to verify the HMAC signature
# of the received Sarif log body.

async def receive_sarif_log(msg: aio_pika.abc.AbstractIncomingMessage) -> None:
    try:
       
      shared_secret = "MySharedSecret-12344$abc!123"
      sig = msg.headers['x-cx-signature']
      alg = msg.headers['x-cx-signature-alg']
      print(f"Received message with signature: {sig} generated using algorithm {alg}")

      h = hmac.new(bytes(shared_secret, 'UTF-8'), msg.body, alg)
      if h.hexdigest() != sig:
          print(f"Calculated signature {h.hexdigest()} is invalid.")
      else:
        print("The signature verified correctly.")

    except BaseException as ex:
        await msg.nack(requeue=False)
    finally:
        await msg.ack()

async def be_an_agent():
  mq_client = await aio_pika.connect_robust("amqp://localhost/sarif")
  async with mq_client.channel() as channel:
      q = await channel.get_queue("SARIF")
      await q.consume(receive_sarif_log)
      while True:
          await asyncio.Future()

if __name__ == "__main__":
  asyncio.run(be_an_agent())
