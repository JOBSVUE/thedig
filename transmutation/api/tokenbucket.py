"""
Token Bucket pattern using celery for rate limit    
taken from https://medium.com/analytics-vidhya/celery-throttling-setting-rate-limit-for-queues-5b5bf16c73ce
"""
from celery import Celery
from kombu import Queue
from queue import Empty
from functools import wraps

from .config import celery_broker

celery_tasks = Celery(__name__, broker=celery_broker)

task_queues = [Queue("github"), Queue("google")]

# per minute rate
rate_limits = {"github": 60, "google": 100}

TIME_UNIT = 60


def setup_queues(celery_tasks, rate_limits: dict):
    # generating queues for all groups with limits, that we defined in dict above
    task_queues += [
        Queue(name + "_tokens", max_length=2) for name, limit in rate_limits.items()
    ]
    celery_tasks.conf.task_queues = task_queues


@celery_tasks.task
def token():
    return 1


@celery_tasks.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # generating auto issuing of tokens for all lmited groups
    for name, limit in rate_limits.items():
        sender.add_periodic_task(
            TIME_UNIT / limit, token.signature(queue=name + "_tokens")
        )


# I really like decorators ;)
def rate_limit(task_group):
    def decorator_func(func):
        @wraps(func)
        def function(self, *args, **kwargs):
            with self.celery_tasks.connection_for_read() as conn:
                # Here I used another higher level method
                # We are getting complete queue interface
                # but in return losing some perfomance because
                # under the hood there is additional work done
                with conn.SimpleQueue(
                    task_group + "_tokens", no_ack=True, queue_opts={"max_length": 2}
                ) as queue:
                    try:
                        # Another advantage is that we can use blocking call
                        # It can be more convenient than calling retry() all the time
                        # However, it depends on the specific case
                        queue.get(block=True, timeout=5)
                        return func(self, *args, **kwargs)
                    except Empty:
                        self.retry(countdown=1)

        return function

    return decorator_func
