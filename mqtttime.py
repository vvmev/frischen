#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getopt
import os
import sys

from time import sleep, time

from frischen import MqttPost


config = {
    'client_id': 'mqtttime',
    'host': 'localhost',
    'port': 1883,
    'topic': 'frischen/time/1hz'
}


def usage():
    print('''Usage: {} [-h hostname] [-p port] [-t topic]
'''.format(os.path.basename(__file__)), file=sys.stderr, end='')
    sys.exit(64)


def main():
    global config

    try:
        options, args = getopt.getopt(
            sys.argv[1:], 'h:p:t:?', ['host', 'port', 'topic', help])
    except getopt.GetoptError as e:
        print('Error parsing command line: {}'.format(e), file=sys.stderr)
        usage()

    for opt, arg in options:
        if opt in ('-h', '--host'):
            config['host'] = arg
        if opt in ('-p', '--port'):
            config['port'] = arg
        if opt in ('-t', '--topic'):
            config['topic'] = arg
        if opt in ('-?', '--help'):
            usage()

    p = MqttPost('{}-{}'.format(config['client_id'], 'post'),
                 config['host'], config['port'])
    i = 0
    while True:
        next = int(time()) + 1 - 0.5 * i
        delay = next - time()
        while delay > 0.0:
            sleep(delay)
            delay = next - time()
        i = 1 if i == 0 else 0
        p.post(config['topic'], [i])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
