import asyncio, logging, time
from threading import Thread, Lock
from traceback import TracebackException


class TaskManager:
    __monitor_lock = Lock()
    __monitored = []
    __bgloop = None
    __thread = None

    @staticmethod
    def log():
        return logging.getLogger("TaskManager")
    
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
        TaskManager.log().debug(f"Callback for finished future {future}.")
        with TaskManager.__monitor_lock:
            TaskManager.__log_future_result(future)
            TaskManager.__monitored.remove(future)

    @staticmethod
    def __log_future_result(future):
        if future.exception() is not None:
            TaskManager.log().exception(future.exception())
            TaskManager.log().error("".join(TracebackException.from_exception(future.exception()).format()))
        else:
            if future.result() is not None:
                TaskManager.log().debug(future.result())


    @staticmethod
    def in_background(coro):
        with TaskManager.__monitor_lock:
            ts = asyncio.run_coroutine_threadsafe(coro, TaskManager.__bgloop)
            ts.add_done_callback(TaskManager.__callback)
            TaskManager.__monitored.append(ts)

    @staticmethod
    async def in_foreground(coro):
        return asyncio.run_coroutine_threadsafe(coro, TaskManager.__bgloop).result()

    @staticmethod
    def wait_for_exit():
        TaskManager.log().info("Gracefully shutting down...")
        while True:
            with TaskManager.__monitor_lock:
                TaskManager.log().debug(f"TaskManager.__monitored: {len(TaskManager.__monitored)}")
                
                if len(TaskManager.__monitored) == 0:
                    break
            time.sleep(1.0)
            


            

