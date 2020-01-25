# -*- coding: utf-8 -*-
# Description: EdgeX Platform netdata python.d module
# Author: Odysseas Lamtzidis (OdysLam)
# SPDX-License-Identifier: GPL-3.0-or-later
# Edgex-API-Version: 1
# Edgex-Version: Fuji

import json
import threading

from collections import namedtuple

try:
    from Queue import Queue
except ImportError:
    from queue import Queue

from bases.FrameworkServices.UrlService import UrlService

METHODS = namedtuple('METHODS', ['get_data', 'url', 'run'])

ORDER = [
    'events_throughput',
    'events_count',
    'devices_number',
    'memory_alloc',
    'memory_malloc',
    'memory_frees',
    'memory_liveObjects'
]

# default module values (can be overridden per job in `config`)
update_every = 5

CHARTS = {
    'events_throughput': {
        'options': [None, 'Events Throughput', 'events/s',
                    'events', 'edgex.events_readings_incr', 'line'],
        'lines': [
            ['events', None, 'incremental'],
            ['readings', None, 'incremental']
        ]
    },
    'events_count': {
        'options': [None, 'Absolute Count', 'events', 'events',
                    'edgex.events_readings_abs', 'line'],
        'lines': [
            ['readings', None, 'absolute'],
            ['events', None, 'absolute']
        ]
    },
    'devices_number': {
        'options': [None, 'devices count', 'devices', 'devices',
                    'edgex.devices_number', 'line'],
        'lines': [
            ['registered_devices', None, 'absolute'],
        ]
    },
    'memory_alloc': {
        'options': [None, 'Alloc',
                    'bytes', 'memory', 'edgex.memory_alloc', 'line'],
        'lines': [
            ['core_data_alloc', 'core_data', 'absolute'],
            ['core_metadata_alloc', 'core_metadata', 'absolute'],
            ['core_command_alloc', 'core_command', 'absolute'],
            ['support_logging_alloc', 'support_logging', 'absolute']
        ]
    },
    'memory_malloc': {
        'options': [None, 'Mallocs', 'heap objects',
                    'memory', 'edgex.memory_malloc', 'line'],
        'lines': [
            ['core_data_malloc', 'core_data', 'incremental'],
            ['core_metadata_malloc', 'core_metadata', 'incremental'],
            ['core_command_malloc', 'core_command', 'incremental'],
            ['support_logging_malloc', 'support_logging', 'incremental']
        ]
    },
    'memory_frees': {
        'options': [None, 'Frees', 'heap objects',
                    'memory', 'edgex.memory_frees', 'line'],
        'lines': [
            ['core_data_frees', 'core_data', 'absolute'],
            ['core_metadata_frees', 'core_metadata', 'absolute'],
            ['core_command_frees', 'core_command', 'absolute'],
            ['support_logging_frees', 'support_logging', 'absolute']
        ]
    },
    'memory_liveObjects': {
        'options': [None, 'LiveObjects', 'heap objects',
                    'memory', 'edgex.memory_liveObjects', 'line'],
        'lines': [
            ['core_data_live_objects', 'core_data', 'absolute'],
            ['core_metadata_live_objects', 'core_metadata', 'absolute'],
            ['core_command_live_objects', 'core_command', 'absolute'],
            ['support_logging_live_objects', 'support_logging', 'absolute']
        ]
    }
}


def get_survive_any(method):
    def w(*args):
        try:
            method(*args)
        except Exception as error:
            self, queue, url = args[0], args[1], args[2]
            self.error("error during '{0}' : {1}".format(url, error))
            queue.put(dict())

    return w


class Service(UrlService):
    def __init__(self, configuration=None, name=None):
        UrlService.__init__(self, configuration=configuration, name=name)
        self.order = ORDER
        self.definitions = CHARTS
        self.url = '{protocol}://{host}'.format(
            protocol=self.configuration.get('protocol', 'http'),
            host=self.configuration.get('host', 'localhost')
        )
        self.edgex_ports = {
            'support_logging': self.configuration.get('port_logging', '48061'),
            'core_data': self.configuration.get('port_data', '48080'),
            'core_metadata': self.configuration.get('port_metadata', '48081'),
            'core_command': self.configuration.get('port_command', '48082')
        }
        self.init_urls()
        self.init_methods()

    def init_urls(self):
        self.url_core_data = '{url}:{port}/api/v1/'.format(
            url=self.url,
            port=self.edgex_ports['core_data']
        )
        self.url_core_metadata = '{url}:{port}/api/v1/'.format(
            url=self.url,
            port=self.edgex_ports['core_metadata']
        )
        self.url_core_command = '{url}:{port}/api/v1/'.format(
            url=self.url,
            port=self.edgex_ports['core_command']
        )
        self.url_support_logging = '{url}:{port}/api/v1/'.format(
            url=self.url,
            port=self.edgex_ports['support_logging']
        )

    def init_methods(self):
        self.methods = [
            METHODS(
                get_data=self._get_core_throughput_events,
                url=self.url_core_data,
                run=self.configuration.get('events_per_second', True),
            ),
            METHODS(
                get_data=self._get_core_throughput_readings,
                url=self.url_core_data,
                run=self.configuration.get('events_per_second', True)
            ),
            METHODS(
                get_data=self._get_device_info,
                url=self.url_core_metadata,
                run=self.configuration.get('number_of_devices', True)
            ),
            METHODS(
                get_data=self._get_metrics_data,
                url=self.url_core_metadata,
                run=self.configuration.get('metrics', True)
            ),
            METHODS(
                get_data=self._get_metrics_data,
                url=self.url_core_data,
                run=self.configuration.get('metrics', True)
            ),
            METHODS(
                get_data=self._get_metrics_data,
                url=self.url_core_command,
                run=self.configuration.get('metrics', True)
            ),
            METHODS(
                get_data=self._get_metrics_data,
                url=self.url_support_logging,
                run=self.configuration.get('metrics', True)
            )
        ]
        return UrlService.check(self)

    def _get_data(self):
        threads = list()
        queue = Queue()
        result = {}
        for method in self.methods:
            if not method.run:
                continue
            th = threading.Thread(
                target=method.get_data,
                args=(queue, method.url),
            )
            th.daemon = True
            th.start()
            threads.append(th)

        for thread in threads:
            thread.join()
            result.update(queue.get())

        return result or None

    @get_survive_any
    def _get_core_throughput_readings(self, queue, url):
        data = {}
        readings_count_url = url + 'reading/count'
        raw = self._get_raw_data(readings_count_url)
        if not raw:
            return queue.put({})
        raw = int(raw)
        data['readings'] = raw
        if 'event' in url:
            data['events'] = raw
        return queue.put(data)

    @get_survive_any
    def _get_core_throughput_events(self, queue, url):
        data = {}
        events_count_url = url + 'event/count'
        raw = self._get_raw_data(events_count_url)
        if not raw:
            return queue.put({})
        raw = int(raw)
        data['events'] = raw
        return queue.put(data)

    @get_survive_any
    def _get_device_info(self, queue, url):
        data = {}
        device_count_url = url + 'device'
        raw = self._get_raw_data(device_count_url)  # json string
        if not raw:
            return queue.put({})
        parsed = json.loads(raw)  # python object
        data['registered_devices'] = len(parsed)  # int
        return queue.put(data)

    @get_survive_any
    def _get_metrics_data(self, queue, url):
        data = {}
        metrics_url = url + 'metrics'
        raw = self._get_raw_data(metrics_url)
        if not raw:
            return queue.put({})
        parsed = json.loads(raw)
        if self.edgex_ports['core_data'] in url:
            data['core_data_alloc'] = parsed["Memory"]["Alloc"]
            data['core_data_malloc'] = parsed["Memory"]["Mallocs"]
            data['core_data_frees'] = parsed["Memory"]["Frees"]
            data['core_data_live_objects'] = parsed["Memory"]["LiveObjects"]
        elif self.edgex_ports['core_metadata'] in url:
            data['core_metadata_alloc'] = parsed["Memory"]["Alloc"]
            data['core_metadata_malloc'] = parsed["Memory"]["Mallocs"]
            data['core_metadata_frees'] = parsed["Memory"]["Frees"]
            data['core_metadata_live_objects'] = parsed["Memory"]["LiveObjects"]
        elif self.edgex_ports['core_command'] in url:
            data['core_command_alloc'] = parsed["Memory"]["Alloc"]
            data['core_command_malloc'] = parsed["Memory"]["Mallocs"]
            data['core_command_frees'] = parsed["Memory"]["Frees"]
        elif self.edgex_ports['support_logging'] in url:
            data['support_logging_alloc'] = parsed["Memory"]["Alloc"]
            data['support_logging_malloc'] = parsed["Memory"]["Mallocs"]
            data['support_logging_frees'] = parsed["Memory"]["Frees"]
            data['support_logging_live_objects'] = parsed["Memory"]["LiveObjects"]
        return queue.put(data)
