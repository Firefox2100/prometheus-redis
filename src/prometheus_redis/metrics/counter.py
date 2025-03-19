"""
Counter metric type.
"""

from prometheus_redis.util import log_exceptions
from .base_metric import BaseMetric, MetricType


class Counter(BaseMetric):
    type = MetricType.COUNTER
    wrapped_functions_names = ['inc', 'set']

    @log_exceptions
    async def _inc(self,
                   value: int,
                   labels: dict[str, str],
                   ):
        group_key = self.metric_group_key
        metric_key = self.get_metric_key(labels)

        pipeline = self.registry.db.pipeline()
        await pipeline.sadd(group_key, metric_key)
        await pipeline.incrby(metric_key, int(value))
        return (await pipeline.execute())[1]

    @log_exceptions
    async def _set(self,
                   value: int,
                   labels: dict[str, str],
                   ):
        group_key = self.metric_group_key
        metric_key = self.get_metric_key(labels)

        pipeline = self.registry.db.pipeline()
        await pipeline.sadd(group_key, metric_key)
        await pipeline.set(metric_key, int(value))
        return (await pipeline.execute())[1]

    async def inc(self,
                  value: int = 1,
                  labels: dict[str, str] = None,
                  ):
        """
        Calculate metric with labels redis key.
        Add this key to set of key for this metric.
        """
        labels = labels or {}
        self._check_labels(labels)

        if not isinstance(value, int):
            raise ValueError(f'Value should be int, got {type(value)}')

        return await self._inc(value, labels)

    async def set(self,
                  value: int = 1,
                  labels: dict[str, str] = None,
                  ):
        """
        Calculate metric with labels redis key.
        Set this key to set of key for this metric.
        """
        labels = labels or {}
        self._check_labels(labels)

        if not isinstance(value, int):
            raise ValueError(f'Value should be int, got {type(value)}')

        return await self._set(value, labels)
