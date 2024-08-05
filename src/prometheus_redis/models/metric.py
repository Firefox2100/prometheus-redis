from redis import Redis
from redis.commands.core import Script

from prometheus_redis.etc.enums import RMetricType
from prometheus_redis.etc.errors import LabelAmountMismatch, MissingLabelValues


class RMetric:
    db: Redis | None = None
    _histogram_update_script: Script | None = None

    def __init__(self,
                 metric_type: RMetricType,
                 metric_name: str,
                 description: str,
                 label_names: list[str] = None,
                 ):
        self.metric_type = metric_type
        self.metric_name = metric_name
        self.description = description

        self.label_names = label_names or []
        self.label_names.sort()

    def to_dict(self) -> dict:
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
    def from_dict(cls, payload: dict):
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

        try:
            assert all(label_name in kwargs.keys() for label_name in self.label_names)
        except AssertionError:
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
            for key in keys:
                self.db.delete(key)


class RCounter(RMetric):
    def __init__(self,
                 metric_name: str,
                 description: str,
                 value: float | dict[str, float] = 0.0,
                 label_names: list[str] = None,
                 ):
        super().__init__(
            metric_type=RMetricType.COUNTER,
            metric_name=metric_name,
            description=description,
            label_names=label_names,
        )

        if label_names:
            # Labels are defined, value has to be a dict
            if value:
                raise LabelAmountMismatch('Initial value must be a dict when label names are defined')
            else:
                self.value = {}
        else:
            self.value = value

    @property
    def value(self) -> float | dict[str, float]:
        if not self.label_names:
            return self.db.get(self.metric_name) or 0.0
        else:
            keys = self.db.keys(f'{self.metric_name}:*')
            return {key: self.db.get(key) or 0.0 for key in keys}

    @value.setter
    def value(self, value):
        if not self.label_names:
            self.db.set(self.metric_name, value)
        else:
            for key, val in value.items():
                self.db.set(key, val)

    def inc(self,
            value=1.0,
            **kwargs,
            ):
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
                 value: float | dict[str, float] = 0.0,
                 label_names: list[str] = None,
                 ):
        super().__init__(
            metric_type=RMetricType.GAUGE,
            metric_name=metric_name,
            description=description,
            label_names=label_names,
        )

        if label_names:
            # Labels are defined, value has to be a dict
            if value:
                raise ValueError('Initial value must be a dict when label names are defined')
            else:
                self.value = {}
        else:
            self.value = value

    @property
    def value(self) -> float | dict[str, float]:
        if not self.label_names:
            return self.db.get(self.metric_name) or 0.0
        else:
            keys = self.db.keys(f'{self.metric_name}:*')
            return {key: self.db.get(key) or 0.0 for key in keys}

    @value.setter
    def value(self, value):
        if not self.label_names:
            self.db.set(self.metric_name, value)
        else:
            for key, val in value.items():
                self.db.set(key, val)

    def set(self,
            value: float,
            **kwargs,
            ):
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

    def inc(self,
            value=1.0,
            **kwargs,
            ):
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

    def dec(self,
            value=1.0,
            **kwargs,
            ):
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
                 buckets: list[float],
                 values: list[int] | dict[str, list[int]] = None,
                 sum_value: float | dict[str, float] = 0.0,
                 label_names: list[str] = None,
                 ):
        super().__init__(
            metric_type=RMetricType.HISTOGRAM,
            metric_name=metric_name,
            description=description,
            label_names=label_names,
        )

        self.buckets = buckets
        self.sum_value = sum_value

        if label_names:
            # Labels are defined, values and sum_value have to be a dict
            if not isinstance(values, dict) or not isinstance(sum_value, dict):
                raise ValueError('Initial values must be a dict when label names are defined')
            else:
                self.values = {}
                self.sum_value = {}
        else:
            self.values = values if values else [0] * len(buckets)

    @property
    def values(self) -> list[int] | dict[str, list[int]]:
        if not self.label_names:
            return self.db.lrange(self.metric_name, 0, -1)
        else:
            keys = self.db.keys(f'{self.metric_name}:*')
            return {key: self.db.lrange(key, 0, -1) for key in keys}

    @values.setter
    def values(self, values):
        if not self.label_names:
            self.db.delete(self.metric_name)
            self.db.rpush(self.metric_name, *values)
        else:
            for key, val in values.items():
                self.db.delete(key)
                self.db.rpush(key, *val)

    @property
    def sum_value(self) -> float | dict[str, float]:
        if not self.label_names:
            return self.db.get(f'{self.metric_name}:sum') or 0.0
        else:
            keys = self.db.keys(f'{self.metric_name}:*')
            return {key: self.db.get(f'{key}:sum') or 0.0 for key in keys}

    @sum_value.setter
    def sum_value(self, sum_value):
        if not self.label_names:
            self.db.set(f'{self.metric_name}:sum', sum_value)
        else:
            for key, val in sum_value.items():
                self.db.set(f'{key}:sum', val)

    def to_dict(self) -> dict:
        payload = super().to_dict()

        payload['buckets'] = self.buckets

        return payload

    @classmethod
    def from_dict(cls, payload: dict):
        return cls(
            metric_name=payload['metricName'],
            description=payload['description'],
            buckets=payload['buckets'],
            values=payload.get('values'),
            sum_value=payload.get('sumValue'),
        )

    def observe(self,
                value: float,
                **kwargs,
                ):
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
