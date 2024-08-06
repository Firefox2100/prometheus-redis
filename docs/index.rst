Prometheus-Redis Documentation
==============================

Prometheus-Redis is a Python implementation of Prometheus metric data structure with Redis as storage backend. It uses the official Prometheus client library for Python, and stores all data in Redis. This allows multiple process, whether they are forked or are completely different code base, to share the same Redis instance and the metrics data within.


.. toctree::
   :maxdepth: 2
   :caption: Contents:


Disclaimer
==========

This is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this software. If not, see http://www.gnu.org/licenses/.

This project also utilizes third party libraries and tools, like Python, prometheus-client, Redis, etc. They are listed under separate licenses, and their copyright and credit should goes to their original authors. This software will not distribute these source code or executables in any form.


Requirements
============

To use this library you will need:

- Python 3.6 or later
- Redis 5.0 or later


Installation
============

This library can be installed from PyPI using pip:

.. code-block:: bash

    pip install prometheus-redis
