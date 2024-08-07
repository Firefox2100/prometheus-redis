from typing import TYPE_CHECKING

from .etc.enums import RMetricType
from .models import RMetric, RCounter, RGauge, RHistogram
from .models import RedisRegistry
from .models import RedisCollector


if TYPE_CHECKING:
    from redis import Redis


__version__ = '0.1.0'


def init_driver(db: 'Redis'):
    RedisRegistry.init_driver(db)
    RMetric.init_driver(db)
