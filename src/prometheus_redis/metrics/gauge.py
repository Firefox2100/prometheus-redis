import asyncio
import collections

from prometheus_redis.util import log_exceptions
from .base_metric import BaseMetric, MetricType


class Gauge(BaseMetric):
    type = MetricType.GAUGE
    wrapped_functions_names = ['inc', 'set']

    default_expire = 60

    def __init__(self, *args,
                 expire=default_expire,
                 refresh_enable=True,
                 gauge_index_key: str = 'GLOBAL_GAUGE_INDEX',
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.gauge_index_key = gauge_index_key
        self.refresh_enable = refresh_enable
        self._refresher_added = False
        self.lock = asyncio.Lock()
        self.gauge_values = collections.defaultdict(lambda: 0.0)
        self.expire = expire
        self.index = None

    async def refresh_values(self):
        async with self.lock:
            for key, value in self.gauge_values.items():
                await self.registry.db.set(
                    key, value, ex=self.expire,
                )

    def add_refresher(self):
        if self.refresh_enable and not self._refresher_added:
            self.registry.add_refresh_function(
                self.refresh_values,
            )
            self._refresher_added = True

    def _set_internal(self, key: str, value: float):
        self.gauge_values[key] = value

    def _inc_internal(self, key: str, value: float):
        self.gauge_values[key] += value

    @log_exceptions
    async def _inc(self, value: float, labels: dict):
        async with self.lock:
            group_key = self.metric_group_key
            labels['gauge_index'] = self.get_gauge_index()
            metric_key = self.get_metric_key(labels)

            pipeline = self.registry.db.pipeline()
            await pipeline.sadd(group_key, metric_key)
            await pipeline.incrbyfloat(metric_key, float(value))
            await pipeline.expire(metric_key, self.expire)
            self._inc_internal(metric_key, float(value))
            result = await pipeline.execute()

        self.add_refresher()

        return result

    @log_exceptions
    async def _set(self, value: float, labels: dict):
        async with self.lock:
            group_key = self.metric_group_key
            labels['gauge_index'] = self.get_gauge_index()
            metric_key = self.get_metric_key(labels)

            pipeline = self.registry.db.pipeline()
            await pipeline.sadd(group_key, metric_key)
            await pipeline.set(
                metric_key,
                float(value),
                ex=self.expire,
            )
            self._set_internal(metric_key, float(value))
            result = await pipeline.execute()

        self.add_refresher()

        return result

    async def inc(self,
            value: float,
            labels: dict = None,
            ):
        labels = labels or {}
        self._check_labels(labels)
        return await self._inc(value, labels)

    async def dec(self, value: float, labels: dict = None):
        labels = labels or {}
        self._check_labels(labels)
        return await self._inc(-value, labels)

    async def set(self, value: float, labels:dict = None):
        labels = labels or {}
        self._check_labels(labels)
        return await self._set(value, labels)

    async def make_gauge_index(self):
        index = await self.registry.db.incr(
            self.gauge_index_key,
        )
        self.registry.add_refresh_function(
            self.refresh_values,
        )
        return index

    async def get_gauge_index(self):
        if self.index is None:
            self.index = await self.make_gauge_index()
        return self.index

    async def cleanup(self):
        async with self.lock:
            group_key = self.metric_group_key
            keys = list(self.gauge_values.keys())

            if len(keys) == 0:
                return

            pipeline = self.registry.db.pipeline()

            await pipeline.srem(group_key, *keys)
            await pipeline.delete(*keys)
            await pipeline.execute()
