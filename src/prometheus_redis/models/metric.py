from redis import Redis
from redis.commands.core import Script
from typing import List, Dict, Union, Optional
from prometheus_redis.etc.enums import RMetricType
from prometheus_redis.etc.errors import LabelAmountMismatch, MissingLabelValues


class RMetric:
    db: Optional[Redis] = None
    _histogram_update_script: Optional[Script] = None

    def __init__(self,
                 metric_type: RMetricType,
                 metric_name: str,
                 description: str,
                 label_names: Optional[List[str]] = None,
                 ):
        self.metric_type = metric_type
        self.metric_name = metric_name
        self.description = description

        self.label_names = label_names or []
        self.label_names.sort()

    def __eq__(self, other):
        if not isinstance(other, RMetric):
            return NotImplemented

        if self.label_names != other.label_names:
            return False

        return all([
            self.metric_type == other.metric_type,
            self.metric_name == other.metric_name,
            self.description == other.description,
        ])

    def to_dict(self) -> Dict:
        payload = {
            'metricType': self.metric_type.value,
            'metricName': self.metric_name,
            'description': self.description,
        }

        self.label_names.sort()

        if self.label_names:
            payload['labelNames'] = self.label_names

        return payload

    @classmethod
    def from_dict(cls, payload: Dict):
        return cls(
            metric_type=RMetricType(payload['metricType']),
            metric_name=payload['metricName'],
            description=payload['description'],
            label_names=payload.get('labelNames'),
        )

    @classmethod
    def init_driver(cls, db: Redis):
        cls.db = db

        histogram_update_script = """
        local key = KEYS[1]
        local indexes = ARGV

        for i, index in ipairs(indexes) do
            local idx = tonumber(index)
            local current_value = redis.call('LINDEX', key, idx)

            if current_value then
                local new_value = tonumber(current_value) + 1
                redis.call('LSET', key, idx, new_value)
            else
                return nil
            end
        end

        return 'OK'
        """
        cls._histogram_update_script = cls.db.register_script(histogram_update_script)

    def _assemble_key(self, **kwargs) -> str:
        """
        Assemble the key for the metric in Redis
        """
        if not self.label_names:
            return self.metric_name

        if not all(label_name in kwargs.keys() for label_name in self.label_names):
            raise MissingLabelValues('Missing label values')

        label_values = [kwargs.get(label_name) for label_name in self.label_names]
        return f'{self.metric_name}:{":".join(label_values)}'

    def clear(self):
        """
        Clear the value of the metric in Redis
        """
        if not self.label_names:
            self.db.delete(self.metric_name)
        else:
            keys = self.db.keys(f'{self.metric_name}:*')
            if keys:
                self.db.delete(*keys)


class RCounter(RMetric):
    def __init__(self,
                 metric_name: str,
                 description: str,
                 value: Union[float, Dict[str, float]] = 0.0,
                 label_names: Optional[List[str]] = None,
                 ):
        super().__init__(
            metric_type=RMetricType.COUNTER,
            metric_name=metric_name,
            description=description,
            label_names=label_names,
        )

        if label_names:
            # Labels are defined, value has to be a dict
            if not isinstance(value, dict):
                raise LabelAmountMismatch('Initial value must be a dict when label names are defined')
            self.value = {}
        else:
            self.value = value

    @property
    def value(self) -> Union[float, Dict[str, float]]:
        if not self.label_names:
            return float(self.db.get(self.metric_name) or 0.0)
        else:
            keys = self.db.keys(f'{self.metric_name}:*')
            return {key.decode('utf-8'): float(self.db.get(key) or 0.0) for key in keys}

    @value.setter
    def value(self, value: Union[float, Dict[str, float]]):
        if not self.label_names:
            self.db.set(self.metric_name, value)
        else:
            for key, val in value.items():
                self.db.set(key, val)

    def inc(self, value: float = 1.0, **kwargs):
        """
        Increment the value of the counter metric
        :param value: The value to increment by
        :param kwargs: The label values
        """
        if not self.label_names:
            self.db.incrbyfloat(self.metric_name, value)
        else:
            key = self._assemble_key(**kwargs)
            self.db.incrbyfloat(key, value)


class RGauge(RMetric):
    def __init__(self,
                 metric_name: str,
                 description: str,
                 value: Union[float, Dict[str, float]] = 0.0,
                 label_names: Optional[List[str]] = None,
                 ):
        super().__init__(
            metric_type=RMetricType.GAUGE,
            metric_name=metric_name,
            description=description,
            label_names=label_names,
        )

        if label_names:
            # Labels are defined, value has to be a dict
            if not isinstance(value, dict):
                raise ValueError('Initial value must be a dict when label names are defined')
            self.value = {}
        else:
            self.value = value

    @property
    def value(self) -> Union[float, Dict[str, float]]:
        if not self.label_names:
            return float(self.db.get(self.metric_name) or 0.0)
        else:
            keys = self.db.keys(f'{self.metric_name}:*')
            return {key.decode('utf-8'): float(self.db.get(key) or 0.0) for key in keys}

    @value.setter
    def value(self, value: Union[float, Dict[str, float]]):
        if not self.label_names:
            self.db.set(self.metric_name, value)
        else:
            for key, val in value.items():
                self.db.set(key, val)

    def set(self, value: float, **kwargs):
        """
        Set the value of the gauge metric
        :param value: The value to set
        :param kwargs: The label values
        """
        if not self.label_names:
            self.db.set(self.metric_name, value)
        else:
            key = self._assemble_key(**kwargs)
            self.db.set(key, value)

    def inc(self, value: float = 1.0, **kwargs):
        """
        Increment the value of the gauge metric
        :param value: The value to increment by
        :param kwargs: The label values
        """
        if not self.label_names:
            self.db.incrbyfloat(self.metric_name, value)
        else:
            key = self._assemble_key(**kwargs)
            self.db.incrbyfloat(key, value)

    def dec(self, value: float = 1.0, **kwargs):
        """
        Decrement the value of the gauge metric
        :param value: The value to decrement by
        :param kwargs: The label values
        """
        if not self.label_names:
            self.db.incrbyfloat(self.metric_name, -value)
        else:
            key = self._assemble_key(**kwargs)
            self.db.incrbyfloat(key, -value)


class RHistogram(RMetric):
    def __init__(self,
                 metric_name: str,
                 description: str,
                 buckets: List[float],
                 values: Optional[Union[List[int], Dict[str, List[int]]]] = None,
                 sum_value: Optional[Union[float, Dict[str, float]]] = 0.0,
                 label_names: Optional[List[str]] = None,
                 ):
        super().__init__(
            metric_type=RMetricType.HISTOGRAM,
            metric_name=metric_name,
            description=description,
            label_names=label_names,
        )

        self.buckets = buckets

        if label_names:
            # Labels are defined, values and sum_value have to be a dict
            if not isinstance(values, dict) or not isinstance(sum_value, dict):
                raise ValueError('Initial values must be a dict when label names are defined')
            self.values = {}
            self.sum_value = {}
        else:
            self.values = values if values else [0] * len(buckets)
            self.sum_value = sum_value

    @property
    def values(self) -> Union[List[int], Dict[str, List[int]]]:
        if not self.label_names:
            return [int(value) for value in self.db.lrange(self.metric_name, 0, -1)]
        else:
            keys = self.db.keys(f'{self.metric_name}:*')
            return {key.decode('utf-8'): [int(v) for v in self.db.lrange(key, 0, -1)] for key in keys}

    @values.setter
    def values(self, values: Union[List[int], Dict[str, List[int]]]):
        if not self.label_names:
            self.db.delete(self.metric_name)
            self.db.rpush(self.metric_name, *values)
        else:
            for key, val in values.items():
                self.db.delete(key)
                self.db.rpush(key, *val)

    @property
    def sum_value(self) -> Union[float, Dict[str, float]]:
        if not self.label_names:
            return float(self.db.get(f'{self.metric_name}:sum') or 0.0)
        else:
            keys = self.db.keys(f'{self.metric_name}:*')
            return {key.decode('utf-8'): float(self.db.get(f'{key}:sum') or 0.0) for key in keys}

    @sum_value.setter
    def sum_value(self, sum_value: Union[float, Dict[str, float]]):
        if not self.label_names:
            self.db.set(f'{self.metric_name}:sum', sum_value)
        else:
            for key, val in sum_value.items():
                self.db.set(f'{key}:sum', val)

    def to_dict(self) -> Dict:
        payload = super().to_dict()
        payload['buckets'] = self.buckets
        return payload

    @classmethod
    def from_dict(cls, payload: Dict):
        return cls(
            metric_name=payload['metricName'],
            description=payload['description'],
            buckets=payload['buckets'],
            values=payload.get('values'),
            sum_value=payload.get('sumValue'),
        )

    def observe(self, value: float, **kwargs):
        """
        Observe a value for the histogram metric
        :param value: The value to observe
        :param kwargs: The label values
        """
        increment_index = []

        if not self.label_names:
            for i, bucket in enumerate(self.buckets):
                if value < bucket:
                    increment_index.append(i)

            self._histogram_update_script(
                keys=[self.metric_name],
                args=increment_index,
            )
            self.db.incrbyfloat(f'{self.metric_name}:sum', value)
        else:
            key = self._assemble_key(**kwargs)

            for i, bucket in enumerate(self.buckets):
                if value < bucket:
                    increment_index.append(i)

            self._histogram_update_script(
                keys=[key],
                args=increment_index,
            )
            self.db.incrbyfloat(f'{key}:sum', value)
