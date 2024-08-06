import json
from typing import List, Optional
from redis import Redis
from prometheus_redis.etc.errors import MetricNotFound
from .metric import RMetric


class RedisRegistry:
    metrics: List[RMetric] = []
    db: Optional[Redis] = None

    def __getitem__(self, item: str) -> RMetric:
        for metric in self.metrics:
            if metric.metric_name == item:
                return metric

        raise MetricNotFound(f'Metric with name {item} not found in the registry')

    @classmethod
    def init_driver(cls, db: Redis):
        cls.db = db

    def register(self, metric: RMetric):
        self.metrics.append(metric)

        if self.db:
            self.db.rpush('metrics', json.dumps(metric.to_dict()))
        else:
            raise RuntimeError("Redis connection is not initialized. Call `init_driver` first.")

    def unregister(self, metric_name: str):
        metric = self[metric_name]

        self.metrics.remove(metric)

        if self.db:
            self.db.lrem('metrics', 0, json.dumps(metric.to_dict()))
        else:
            raise RuntimeError("Redis connection is not initialized. Call `init_driver` first.")

    def load_registry(self):
        if not self.db:
            raise RuntimeError("Redis connection is not initialized. Call `init_driver` first.")

        metrics = self.db.lrange('metrics', 0, -1)

        for metric in metrics:
            metric_dict = json.loads(metric)
            self.metrics.append(RMetric.from_dict(metric_dict))
