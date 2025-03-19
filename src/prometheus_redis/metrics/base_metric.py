"""
Base class for all metrics
"""

import base64
import json
from enum import Enum
from functools import partial

from prometheus_redis.registry import REGISTRY, RedisRegistry


class MetricType(Enum):
    """
    Type of collected metrics
    """
    COUNTER = 'counter'
    GAUGE = 'gauge'
    HISTOGRAM = 'histogram'
    SUMMARY = 'summary'


class LabelWrapper:
    """
    Wrap functions and put 'labels' argument to it.
    """
    __slot__ = (
        "instance",
        "labels",
        "wrapped_functions_names",
    )

    def __init__(self,
                 instance,
                 labels: dict,
                 wrapped_functions_names: list[str],
                 ):
        self.instance = instance
        self.labels = labels
        self.wrapped_functions_names = wrapped_functions_names

    def __getattr__(self, wrapped_function_name):
        if wrapped_function_name not in self.wrapped_functions_names:
            raise TypeError(f'Labels work with functions {self.wrapped_functions_names} only')
        wrapped_function = getattr(self.instance, wrapped_function_name)
        return partial(wrapped_function, labels=self.labels)


class BaseMetric:
    """
    Base class for all metrics
    """
    metric_type: MetricType = None
    wrapped_functions_names = []

    def __init__(self,
                 name: str,
                 documentation: str,
                 labelnames: list = None,
                 registry: RedisRegistry = REGISTRY,
                 ):
        self.documentation = documentation
        self.labelnames = labelnames or []
        self.name = name
        self.registry = registry
        self.registry.add_metric(self)

    @property
    def doc_string(self) -> str:
        """
        Return the Prometheus formatted document string
        """
        return (f'# HELP {self.name} {self.documentation}\n'
                f'# TYPE {self.name} {self.metric_type.value}')

    @property
    def metric_group_key(self):
        """
        Get the key for metric group in redis
        """
        return f'{self.name}_group'

    def get_metric_key(self, labels, suffix: str = None):
        """
        Get a key for one label in redis
        """
        packed_labels = base64.b64encode(
            json.dumps(labels, sort_keys=True).encode()
        ).decode()

        return f'{self.name}{suffix or ""}:{packed_labels}'

    @staticmethod
    def parse_metric_key(key: bytes) -> (str, dict):
        """
        Get the metric name and labels from a redis key
        """
        name, packed_labels = key.decode().split(':', maxsplit=1)
        labels = json.loads(base64.b64decode(packed_labels).decode())

        return name, labels

    def _check_labels(self, labels):
        if set(labels.keys()) != set(self.labelnames):
            raise ValueError(
                f'Expect define all labels: {", ".join(self.labelnames)}.'
                f'Got only: {", ".join(labels.keys())}'
            )

    def labels(self, *args, **kwargs):
        """
        Add labels to the metric

        The labels should be passed as keyword arguments, for
        example, `metric.labels(key1='value1', key2='value2')`
        """
        labels = dict(zip(self.labelnames, args))
        labels.update(kwargs)
        self._check_labels(labels)
        return LabelWrapper(
            instance=self,
            labels=labels,
            wrapped_functions_names=self.wrapped_functions_names,
        )

    async def collect(self) -> list[str]:
        """
        Collect the metric values

        This is the main method used to generate the Prometheus output
        """
        db = self.registry.db
        group_key = self.metric_group_key
        members = await db.smembers(group_key)

        result: list[str] = []
        for metric_key in members:
            name, labels = self.parse_metric_key(metric_key)
            value = await db.get(metric_key)
            if value is None:
                await db.srem(group_key, metric_key)
                continue

            value = value.decode()

            if labels is None:
                labels_str = ''
            else:
                labels_str = ','.join([
                    f'{key}="{labels[key]}"'
                    for key in sorted(labels.keys())
                ])
                if labels_str:
                    labels_str = f'{{{labels_str}}}'

            result.append(f'{name}{labels_str} {value}')
        return result

    async def cleanup(self):
        pass
