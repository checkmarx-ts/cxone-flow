import asyncio, logging
from threading import Thread, Lock


class TaskManager:
    __log = logging.getLogger("TaskManager")

    __monitor_lock = Lock()
    __monitored = []
    __bgloop = None
    __thread = None

    @staticmethod
    def __thread_proc():
        asyncio.set_event_loop(TaskManager.__bgloop)
        TaskManager.__bgloop.run_forever()

    @staticmethod
    def bootstrap():
        TaskManager.__bgloop = asyncio.new_event_loop()
        TaskManager.__thread = Thread(target=TaskManager.__thread_proc, daemon=True)
        TaskManager.__thread.start()
   

    @staticmethod
    def loop():
        return TaskManager.__bgloop

    @staticmethod
    def stop():
        TaskManager.__bgloop.stop()

    @staticmethod
    def __callback(future):
        with TaskManager.__monitor_lock:
            TaskManager.__log_future_result(future)
            TaskManager.__monitored.remove(future)

    @staticmethod
    def __log_future_result(future):
        if future.exception() is not None:
            TaskManager.__log.error(future.exception())
        else:
            TaskManager.__log.debug(future.result())


    @staticmethod
    def in_background(coro):
        with TaskManager.__monitor_lock:
            ts = asyncio.run_coroutine_threadsafe(coro, TaskManager.__bgloop)
            ts.add_done_callback(TaskManager.__callback)
            TaskManager.__monitored.append(ts)

    @staticmethod
    async def wait_for_exit():
        with TaskManager.__monitor_lock:
            TaskManager.__log.info("Gracefully shutting down...")
            done = await TaskManager.gather(TaskManager.__monitored, return_exceptions=True)
            for f in done:
                TaskManager.__log_future_result(f)
            

