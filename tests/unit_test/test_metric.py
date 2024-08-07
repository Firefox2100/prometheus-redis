import pytest
from deepdiff import DeepDiff

from prometheus_redis import RMetric, RMetricType
from prometheus_redis.etc.errors import MissingLabelValues


@pytest.fixture
def r_metric():
    return RMetric(
        metric_type=RMetricType.COUNTER,
        metric_name='test_metric',
        description='test description',
    )


@pytest.fixture
def r_metric_with_label():
    return RMetric(
        metric_type=RMetricType.COUNTER,
        metric_name='test_metric',
        description='test description',
        label_names=['label2', 'label1', 'label3'],
    )


class TestRMetric:
    def test_init(self):
        r_metric = RMetric(
            metric_type=RMetricType.COUNTER,
            metric_name='test_metric',
            description='test description',
        )

        assert r_metric.metric_type == RMetricType.COUNTER
        assert r_metric.metric_name == 'test_metric'
        assert r_metric.description == 'test description'

    def test_init_with_label(self):
        r_metric = RMetric(
            metric_type=RMetricType.COUNTER,
            metric_name='test_metric',
            description='test description',
            label_names=['label2', 'label1', 'label3'],
        )

        assert r_metric.metric_type == RMetricType.COUNTER
        assert r_metric.metric_name == 'test_metric'
        assert r_metric.description == 'test description'
        assert r_metric.label_names == ['label1', 'label2', 'label3']

    def test_eq(self,
                r_metric,
                r_metric_with_label,
                ):
        assert r_metric == RMetric(
            metric_type=RMetricType.COUNTER,
            metric_name='test_metric',
            description='test description',
        )

        assert r_metric_with_label == RMetric(
            metric_type=RMetricType.COUNTER,
            metric_name='test_metric',
            description='test description',
            label_names=['label1', 'label2', 'label3'],
        )

        assert r_metric != r_metric_with_label
        assert r_metric != 'something else'

    def test_to_dict(self,
                     r_metric,
                     r_metric_with_label,
                     ):
        assert not DeepDiff(
            r_metric.to_dict(),
            {
                'metricType': 'counter',
                'metricName': 'test_metric',
                'description': 'test description',
            }
        )

        assert not DeepDiff(
            r_metric_with_label.to_dict(),
            {
                'metricType': 'counter',
                'metricName': 'test_metric',
                'description': 'test description',
                'labelNames': ['label1', 'label2', 'label3'],
            }
        )

    def test_from_dict(self,
                       r_metric,
                       r_metric_with_label,
                       ):
        assert RMetric.from_dict({
                'metricType': 'counter',
                'metricName': 'test_metric',
                'description': 'test description',
            }) == r_metric

        assert RMetric.from_dict({
                'metricType': 'counter',
                'metricName': 'test_metric',
                'description': 'test description',
                'labelNames': ['label1', 'label2', 'label3'],
            }) == r_metric_with_label

    def test_assemble_key(self,
                          r_metric,
                          r_metric_with_label,
                          ):
        assert r_metric._assemble_key() == 'test_metric'
        assert r_metric._assemble_key(
            label1='value1',
            label2='value2',
            label3='value3',
        ) == 'test_metric'

        with pytest.raises(MissingLabelValues):
            r_metric_with_label._assemble_key()

        assert r_metric_with_label._assemble_key(
            label1='value1',
            label2='value2',
            label3='value3',
        ) == 'test_metric:value1:value2:value3'
