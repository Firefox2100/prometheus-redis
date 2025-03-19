import time
import asyncio
import inspect
import redis.asyncio as redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger


class AsyncRefresher:
    def __init__(self, refresh_period=30.0, timeout_granule=1):
        """
        Fully async, non-blocking refresher using APScheduler.

        :param refresh_period: Time interval (seconds) for executing refresh functions.
        :param timeout_granule: Minimum interval (seconds) between checks.
        """
        self.refresh_period = refresh_period
        self.timeout_granule = timeout_granule
        self._refresh_functions = []
        self._lock = asyncio.Lock()  # Ensures only one execution at a time
        self._scheduler = AsyncIOScheduler()
        self._last_refresh_time = 0  # Tracks last execution time

    def start(self):
        """
        Starts the refresher using APScheduler.
        """
        self._scheduler.start()
        self._scheduler.add_job(
            self.refresh,
            trigger=IntervalTrigger(seconds=self.timeout_granule),
            id='refresh_cycle',
            replace_existing=True
        )

    def stop(self):
        """
        Stops the refresher and clears all registered functions.
        """
        self._scheduler.remove_job('refresh_cycle')
        self._scheduler.shutdown()
        self._refresh_functions.clear()

    async def refresh(self):
        """
        Executes all registered refresh functions while ensuring the interval condition is met.
        """
        async with self._lock:
            now = time.time()
            if now - self._last_refresh_time < self.refresh_period:
                return  # Skip execution if not enough time has passed

            self._last_refresh_time = now
            tasks = []
            for func in self._refresh_functions:
                if inspect.iscoroutinefunction(func):
                    tasks.append(asyncio.create_task(func()))
                else:
                    func()

            if tasks:
                await asyncio.gather(*tasks)

    def add_refresh_function(self, func: callable):
        """
        Registers a function to be periodically executed.

        :param func: An async function to call when refreshed.
        """
        self._refresh_functions.append(func)


class RedisRegistry:
    def __init__(self,
                 db: redis.Redis | redis.RedisCluster = None,
                 ):
        self._metrics = []
        self._refresher = AsyncRefresher()
        self.db = db

    def output(self) -> str:
        payload = []
        for metric in self._metrics:
            payload.append(metric.doc_string())

            ms = metric.collect()
            payload += sorted(ms)

        return "\n".join(payload)

    def add_metric(self, *metrics):
        existing_names = set([
            m.name for m in self._metrics
        ])
        new_metrics = set([
            m.name for m in metrics
        ])

        duplicates = existing_names.intersection(new_metrics)

        if duplicates:
            raise ValueError("Metrics {} already added".format(
                ", ".join(duplicates),
            ))

        for m in metrics:
            self._metrics.append(m)

    def add_refresh_function(self, func: callable):
        """
        Registers a function to be periodically executed.

        :param func: An async function to call when refreshed.
        """
        self._refresher.add_refresh_function(func)

    def stop(self):
        self._refresher.stop()

        for metric in self._metrics:
            metric.cleanup()

        self._metrics = []


REGISTRY = RedisRegistry()
