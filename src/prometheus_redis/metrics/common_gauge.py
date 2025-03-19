"""
CommonGauge metric implementation.
"""

from prometheus_redis.registry import RedisRegistry, REGISTRY
from prometheus_redis.util import log_exceptions
from .base_metric import BaseMetric, MetricType


class CommonGauge(BaseMetric):
    """
    A gauge that is shared between multiple processes.
    """
    metric_type = MetricType.GAUGE
    wrapped_functions_names = ['set', 'inc', 'dec']

    def __init__(self,
                 name: str,
                 documentation: str,
                 labelnames: list = None,
                 registry: RedisRegistry=REGISTRY,
                 expire: int = None,
                 ):
        """
        Construct CommonGauge metric.

        :param name: Name of the metric
        :param documentation: The metric description
        :param labelnames: list of metric labels
        :param registry: the Registry object collect Metric for representation
        :param expire: equivalent Redis `expire`; after that timeout Redis delete key.
        It's useful when you want to know if metric was not updated in a long time.
        """
        super().__init__(
            name=name,
            documentation=documentation,
            labelnames=labelnames,
            registry=registry,
        )
        self._expire = expire

    @log_exceptions
    async def _set(self,
                   value: float,
                   labels: dict[str, str],
                   expire: int = None,
                   ):
        group_key = self.metric_group_key
        metric_key = self.get_metric_key(labels)

        pipeline = self.registry.db.pipeline()
        await pipeline.sadd(group_key, metric_key)
        await pipeline.set(metric_key, value, ex=expire)
        return await pipeline.execute()

    @log_exceptions
    async def _inc(self,
                   value: float,
                   labels: dict[str, str],
                   expire: int = None,
                   ):
        group_key = self.metric_group_key
        metric_key = self.get_metric_key(labels)
        pipeline = self.registry.db.pipeline()
        await pipeline.sadd(group_key, metric_key)
        await pipeline.incrbyfloat(metric_key, float(value))
        if expire:
            await pipeline.expire(metric_key, expire)
        return (await pipeline.execute())[1]

    async def set(self,
            value: float,
            labels: dict[str, str] = None,
            expire: int = None,
            ):
        labels = labels or {}
        self._check_labels(labels)
        if value is None:
            raise ValueError('value can not be None')

        await self._set(value, labels, expire=expire or self._expire)

    async def inc(self,
                  value: float = 1,
                  labels: dict[str, str] = None,
                  expire: int = None,
                  ):
        labels = labels or {}
        self._check_labels(labels)
        return await self._inc(value, labels, expire=expire or self._expire)

    async def dec(self,
                  value: float = 1,
                  labels: dict[str, str] = None,
                  expire: int = None,
                  ):
        labels = labels or {}
        self._check_labels(labels)
        return await self._inc(-value, labels, expire=expire or self._expire)
