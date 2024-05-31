from task_management import TaskManager
import os
from config import get_workers_count, get_log_level

workers = get_workers_count()

timeout = 90
graceful_timeout=600

max_requests = 500

accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
logLevel = get_log_level()


def worker_exit(server, worker):
    TaskManager.wait_for_exit()

