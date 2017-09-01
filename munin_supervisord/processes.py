#!/usr/bin/env python
# encoding: utf-8

"""Munin Plugin to monitor stats for Supervisord processes.

Multigraph Plugin - Graph Structure

    - supervisord_processes_cpu_percent_avg
    - supervisord_processes_cpu_percent_max
    - supervisord_processes_memory_usage
    - supervisord_processes_num_fds
    - supervisord_processes_num_threads
    - supervisord_processes_num_connections
    - supervisord_processes_num_context_switches_voluntary
    - supervisord_processes_num_context_switches_involuntary


Environment Variables

    url: Supervisord xmlrpc url


Example:
    [supervisord_processes]
    user sonemone
    env.url unix:///var/run/supervisord.sock

"""

import os
import sys
import xmlrpclib
from collections import defaultdict
from pymunin import MuninGraph, MuninPlugin, muninMain
import psutil
import supervisor.xmlrpc


__author__ = "gordol"
__copyright__ = "ratazzi <ratazzi.potts@gmail.com>"
__credits__ = ["Thomas Gordon Lowrey IV <linuxinit@gmail.com>"]
__license__ = "MIT License"
__version__ = "0.0.2"
__maintainer__ = "gordol"
__email__ = "linuxinit@gmail.com"
__status__ = "Development"


class MuninSupervisordProcessStatsPlugin(MuninPlugin):
    plugin_name = 'supervisord_processes'
    isMultigraph = True
    isMultiInstance = True

    def __init__(self, argv=(), env=None, debug=False):
        MuninPlugin.__init__(self, argv, env, debug)

        graphs = [
            ('supervisord_processes_memory_usage', 'Memory usage', 'Memory usage', 'Memory usage (MiB)', 'LINE2', 'GAUGE', None),
            ('supervisord_processes_cpu_percent_avg', 'CPU utilization as a percentage (avg)', 'CPU utilization as a percentage (avg)', 'Avg CPU percentage', 'LINE2', 'GAUGE', None),
            ('supervisord_processes_cpu_percent_max', 'CPU utilization as a percentage (max)', 'CPU utilization as a percentage (max)', 'Max CPU percentage', 'LINE2', 'GAUGE', None),
            ('supervisord_processes_num_context_switches_involuntary', 'Context switches (involuntary)', 'Context switches (involuntary)', 'Voluntary context Switches', 'LINE2', 'GAUGE', None),
            ('supervisord_processes_num_context_switches_voluntary', 'Context switches (voluntary)', 'Context switches (voluntary)', 'Voluntary context Switches', 'LINE2', 'GAUGE', None),
            ('supervisord_processes_num_fds', 'File descriptors used', 'File descriptors used', None, 'LINE2', 'GAUGE', '--lower-limit 0'),
            ('supervisord_processes_num_threads', 'Threads currently used', 'Threads currently used', None, 'LINE2', 'GAUGE', '--lower-limit 0'),
            ('supervisord_processes_num_connections', 'Socket connections opened', 'Socket connections opened', None, 'LINE2', 'GAUGE', '--lower-limit 0')
        ]

        self._category = 'supervisord'
        transport = supervisor.xmlrpc.SupervisorTransport(None, None, serverurl=self.envGet('url'))
        proxy = xmlrpclib.ServerProxy('http://127.0.0.1', transport=transport)
        # print proxy.supervisor.getState()
        self.identity = '{0}_{1}'.format(proxy.supervisor.getIdentification(), proxy.supervisor.getPID())
        self.entries = proxy.supervisor.getAllProcessInfo()
        self._stats = defaultdict(dict)

        for (graph_name, graph_title, graph_info, graph_vlabel, graph_draw, graph_type, graph_args) in graphs:
            if self.graphEnabled(graph_name):
                graph = MuninGraph('Supervisord - {0}'.format(graph_title),
                                   self._category, info=graph_info, vlabel=graph_vlabel, args=graph_args)

                for entry in self.entries:
                    if entry['statename'] not in ('RUNNING',):
                        continue

                    label_fmt = entry['group'] == entry['name'] and '{name}.{pid}' or '{group}:{name}'
                    graph.addField(entry['name'],
                                   label_fmt.format(**entry), draw=graph_draw,
                                   type=graph_type, info=graph_info,
                                   min=graph_name.startswith('supervisord_processes_num_') and 0 or None)

                if graph.getFieldCount() > 0:
                    self.appendGraph(graph_name, graph)

    def retrieveVals(self):
        """Retrieve values for graphs."""
        attrs = ('num_fds', 'num_ctx_switches', 'num_threads', 'memory_percent')
        for entry in self.entries:
            try:
                p = psutil.Process(entry['pid'])
                data = p.as_dict(attrs=attrs)
                cpu_usages = []
                #sample for ~2 seconds
                for i in range(20):
                    cpu_usages.append(p.cpu_percent(interval=0.1))

                data['cpu_percent_max'] = float(max(cpu_usages))
                data['cpu_percent_avg'] = float(sum(cpu_usages))/len(cpu_usages)

                # memory usage
                if self.graphEnabled('supervisord_processes_memory_usage')\
                        and data['memory_percent'] is not None:
                    memory_usage = (psutil.virtual_memory().total / 1024 / 1024)\
                        * data['memory_percent'] / 100
                    self._stats['supervisord_processes_memory_usage'][entry['name']] = memory_usage

                # cpu percent avg
                if self.graphEnabled('supervisord_processes_cpu_percent_avg'):
                    self._stats['supervisord_processes_cpu_percent_avg'][entry['name']] = data['cpu_percent_avg']

                # voluntary context switches
                if self.graphEnabled('supervisord_processes_num_context_switches_voluntary'):
                    self._stats['supervisord_processes_num_context_switches_voluntary'][entry['name']] = data['num_ctx_switches'].voluntary

                # involuntary context switches
                if self.graphEnabled('supervisord_processes_num_context_switches_involuntary'):
                    self._stats['supervisord_processes_num_context_switches_involuntary'][entry['name']] = data['num_ctx_switches'].involuntary

                # cpu percent max
                if self.graphEnabled('supervisord_processes_cpu_percent_max'):
                    self._stats['supervisord_processes_cpu_percent_max'][entry['name']] = data['cpu_percent_max']

                # num threads
                if self.graphEnabled('supervisord_processes_num_threads'):
                    self._stats['supervisord_processes_num_threads'][entry['name']] = data['num_threads']

                # num fds
                if self.graphEnabled('supervisord_processes_num_fds'):
                    self._stats['supervisord_processes_num_fds'][entry['name']] = data['num_fds']

                # num connections
                try:
                    if self.graphEnabled('supervisord_processes_num_connections'):
                        num_connections = len(p.connections())
                        self._stats['supervisord_processes_num_connections'][entry['name']] = num_connections
                except psutil.AccessDenied:
                    pass

            except psutil.NoSuchProcess:
                continue

        for graph_name in self.getGraphList():
            for field_name in self.getGraphFieldList(graph_name):
                self.setGraphVal(graph_name, field_name, self._stats[graph_name].get(field_name))

    def autoconf(self):
        """Implements Munin Plugin Auto-Configuration Option.

        @return: True if plugin can be  auto-configured, False otherwise.

        """
        return False


def main():
    sys.exit(muninMain(MuninSupervisordProcessStatsPlugin))


if __name__ == '__main__':
    main()
