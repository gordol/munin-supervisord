Munin plugins for Supervisord
=============================

Features
--------

* CPU utilization as a percentage (average, and max)
* File descriptors used
* Memory usage
* Socket connections opened
* Threads currently used
* Context switches (voluntary and involuntary)

Basic Usage
-----------

Edit /etc/munin/plugin-conf.d/supervisord_process::

    [supervisord_process]
    user root
    env.url unix:///var/run/supervisor.sock
