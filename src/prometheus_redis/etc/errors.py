class PrometheusRedisException(Exception):
    pass


class MetricNotFound(PrometheusRedisException):
    pass


class LabelAmountMismatch(PrometheusRedisException, ValueError):
    pass


class MissingLabelValues(PrometheusRedisException, ValueError):
    pass
