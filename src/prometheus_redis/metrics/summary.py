from functools import partial

from prometheus_redis.util import timer, log_exceptions
from .base_metric import BaseMetric, MetricType


class Summary(BaseMetric):
    type = MetricType.SUMMARY
    wrapped_functions_names = ['observe']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeit = partial(timer, metric_callback=self.observe)

    @log_exceptions
    async def _observer(self,
                        value,
                        labels: dict[str, str],
                        ):
        group_key = self.metric_group_key
        sum_metric_key = self.get_metric_key(labels, "_sum")
        count_metric_key = self.get_metric_key(labels, "_count")

        pipeline = self.registry.db.pipeline()
        await pipeline.sadd(group_key, count_metric_key, sum_metric_key)
        await pipeline.incrbyfloat(sum_metric_key, float(value))
        await pipeline.incr(count_metric_key)
        return (await pipeline.execute())[1]

    async def observe(self,
                      value,
                      labels: dict[str, str] = None,
                      ):
        labels = labels or {}
        self._check_labels(labels)

        return await self._observer(value, labels)
