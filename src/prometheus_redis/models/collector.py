from typing import Iterable
from prometheus_client import Metric
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, HistogramMetricFamily
from prometheus_client.registry import Collector

from prometheus_redis.etc.enums import RMetricType
from .registry import RedisRegistry
from .metric import RCounter, RGauge, RHistogram


class RedisCollector(Collector):
    def _collect_counter(self, metric: RCounter) -> CounterMetricFamily:
        if not metric.label_names:
            counter = CounterMetricFamily(
                name=metric.metric_name,
                documentation=metric.description
            )
            counter.add_metric([], metric.value)
        else:
            counter = CounterMetricFamily(
                name=metric.metric_name,
                documentation=metric.description,
                labels=metric.label_names,
            )

            for k, v in metric.value.items():
                labels = k.split(':')[1:]
                counter.add_metric(labels, v)

        return counter

    def _collect_gauge(self, metric: RGauge) -> GaugeMetricFamily:
        if not metric.label_names:
            gauge = GaugeMetricFamily(
                name=metric.metric_name,
                documentation=metric.description
            )
            gauge.add_metric([], metric.value)
        else:
            gauge = GaugeMetricFamily(
                name=metric.metric_name,
                documentation=metric.description,
                labels=metric.label_names,
            )

            for k, v in metric.value.items():
                labels = k.split(':')[1:]
                gauge.add_metric(labels, v)

        return gauge

    def _collect_histogram(self, metric: RHistogram) -> HistogramMetricFamily:
        histogram = HistogramMetricFamily(
            name=metric.metric_name,
            documentation=metric.description,
            labels=metric.label_names,
        )

        if not metric.label_names:
            bucket_counts = {str(bucket): 0 for bucket in metric.buckets}
            cumulative_count = 0

            for value, count in zip(metric.buckets, metric.values):
                cumulative_count += count
                bucket_counts[str(value)] = cumulative_count

            histogram.add_metric([], bucket_counts, sum_value=metric.sum_value)
        else:
            for k, values in metric.values.items():
                labels = k.split(':')[1:]  # Exclude the metric name from labels
                bucket_counts = {str(bucket): 0 for bucket in metric.buckets}
                cumulative_count = 0

                for value, count in zip(metric.buckets, values):
                    cumulative_count += count
                    bucket_counts[str(value)] = cumulative_count

                sum_value = metric.sum_value.get(k, 0.0)
                histogram.add_metric(labels, bucket_counts, sum_value=sum_value)

        return histogram

    def collect(self) -> Iterable[Metric]:
        for r_metric in RedisRegistry.metrics:
            if r_metric.metric_type == RMetricType.COUNTER:
                if not isinstance(r_metric, RCounter):
                    raise RuntimeError(f"Metric {r_metric.metric_name} is not a Counter")

                yield self._collect_counter(r_metric)
            elif r_metric.metric_type == RMetricType.GAUGE:
                if not isinstance(r_metric, RGauge):
                    raise RuntimeError(f"Metric {r_metric.metric_name} is not a Gauge")

                yield self._collect_gauge(r_metric)
            elif r_metric.metric_type == RMetricType.HISTOGRAM:
                if not isinstance(r_metric, RHistogram):
                    raise RuntimeError(f"Metric {r_metric.metric_name} is not a Histogram")

                yield self._collect_histogram(r_metric)
