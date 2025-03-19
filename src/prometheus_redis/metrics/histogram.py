"""
Histogram metric implementation.
"""

import json
from functools import partial

from prometheus_redis.util import timer, log_exceptions
from .base_metric import BaseMetric, MetricType


class Histogram(BaseMetric):
    type = MetricType.HISTOGRAM
    wrapped_functions_names = ['observe']

    def __init__(self,
                 *args,
                 buckets: list,
                 **kwargs,
                 ):
        super().__init__(*args, **kwargs)

        self.buckets = sorted(buckets, reverse=True)
        self.timeit = partial(timer, metric_callback=self.observe)

    @log_exceptions
    async def _observe(self,
                       value: float,
                       labels: dict[str, str],
                       ):
        group_key = self.metric_group_key
        sum_key = self.get_metric_key(labels, '_sum')
        counter_key = self.get_metric_key(labels, '_count')

        pipeleine = self.registry.db.pipeline()

        for bucket in self.buckets:
            if value > bucket:
                break
            labels['le'] = bucket
            bucket_key = self.get_metric_key(labels, '_bucket')

            await pipeleine.sadd(group_key, bucket_key)
            await pipeleine.incr(bucket_key)

        await pipeleine.sadd(group_key, sum_key, counter_key)
        await pipeleine.incr(counter_key)
        await pipeleine.incrbyfloat(sum_key, float(value))

        return await pipeleine.execute()

    async def _get_missing_metric_values(self):
        db = self.registry.db
        group_key = self.metric_group_key
        members = await db.smembers(group_key)
        missing_metrics_values = set(
            json.dumps({'le': b}) for b in self.buckets
        )
        groups = set('{}')

        # If flag is raised then we should add
        # *_sum and *_count values for empty labels.
        sc_flag = True

        for metric_key in members:
            _, labels = self.parse_metric_key(metric_key)
            key = json.dumps(labels, sort_keys=True)

            if 'le' in labels:
                del labels['le']

            group = json.dumps(labels, sort_keys=True)
            if group == '{}':
                sc_flag = False

            if group not in groups:
                for b in self.buckets:
                    labels['le'] = b
                    missing_metrics_values.add(
                        json.dumps(labels, sort_keys=True)
                    )
                groups.add(group)

            if key in missing_metrics_values:
                missing_metrics_values.remove(key)

        output = []

        for ls in missing_metrics_values:
            labels_str = ",".join([
                f'{key}="{json.loads(ls)[key]}"'
                for key in sorted(json.loads(ls).keys())
            ])
            if labels_str:
                labels_str = f'{{{labels_str}}}'

            output.append(f'{self.name}_bucket{labels_str} 0')

        if sc_flag:
            output.append(f'{self.name}_sum 0')
            output.append(f'{self.name}_count 0')

        return output

    async def observe(self,
                      value: float,
                      labels: dict[str, str] = None,
                      ):
        """
        Observe a value for the histogram.
        """
        labels = labels or {}
        self._check_labels(labels)
        return await self._observe(value, labels)

    async def collect(self) -> list[str]:
        """
        This is the main method used to generate the Prometheus output

        Overridden to add missing bucket values.
        """
        redis_metrics = await super().collect()
        missing_values = await self._get_missing_metric_values()

        return redis_metrics + missing_values
