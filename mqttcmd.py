#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getopt
import os
import sys

from frischen import MqttMonitor, MqttPost


config = {
    'client_id': 'mqttcmd',
    'host': 'localhost',
    'port': 1883,
    'timestamp': True,
}


def usage():
    print('''Usage: {} [-h hostname] [-p port] [-T] command [param...]

Commands:
    monitor topic...
        Print all messages from the selected topic. Hit ^C to stop.
        Topic can contain the standard MQTT wildcards: single level + for a
        single topic segment, or # for all topics below a topic. Examples:
            $SYS/#          all system topics
            frischen/adorf/1/currentposition
            frischen/adorf/+/currentposition
            frischen/adorf/#
    post topic message...
        Post one or more messages to the topic.
'''.format(os.path.basename(__file__)), file=sys.stderr, end='')
    sys.exit(64)


def cmd_monitor(args):
    if len(args) < 1:
        print('You need to specify at least one topic.', file=sys.stderr)
        usage()
    m = MqttMonitor('{}-{}'.format(config['client_id'], 'monitor'),
                    topics=args, host=config['host'], port=config['port'],
                    timestamp=config['timestamp'])
    m.monitor()


def cmd_post(args):
        if len(args) < 2:
            print('must specify least the topic and one message',
                  file=sys.stderr)
            usage()
        p = MqttPost('{}-{}'.format(config['client_id'], 'post'),
                     config['host'], config['port'])
        p.post(args[0], args[1:])


def main():
    global config

    try:
        options, args = getopt.getopt(
            sys.argv[1:], 'h:p:T?', ['host', 'port', help])
    except getopt.GetoptError as e:
        print('Error parsing command line: {}'.format(e), file=sys.stderr)
        usage()

    for opt, arg in options:
        if opt in ('-h', '--host'):
            config['host'] = arg
        if opt in ('-p', '--port'):
            config['port'] = arg
        if opt in ('-T', '--no-timestamp'):
            config['timestamp'] = False
        if opt in ('-?', '--help'):
            usage()

    if len(args) < 1:
        print('Missing command.', file=sys.stderr)
        usage()

    cmd = args.pop(0)
    if cmd == 'monitor':
        cmd_monitor(args)
    elif cmd == 'post':
        cmd_post(args)
    else:
        usage()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
