#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getopt
import os
import sys

from datetime import datetime

from colored import attr, bg, fg
import paho.mqtt.client as mqtt

config = {
    'host': 'localhost',
    'port': 1883,
    'timestamp': False,
}


class MqttMonitor:
    def __init__(self, config, topics):
        self.host = config['host']
        self.port = config['port']
        self.timestamp = config['timestamp']
        self.topics = topics
        self.client = mqtt.Client(client_id="mqtt-monitor")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            print('Unable to connect to broker {}:{}: {}'.format(
                self.host, self.port, rc))
            sys.exit(64)
        for t in self.topics:
            client.subscribe(t)

    def on_message(self, client, userdata, msg):
        if self.timestamp:
            ts = datetime.now().strftime('%H:%M:%S.%f ')
        else:
            ts = ''
        print('{}{}{}{}: {}'.format(
            ts, fg('green'), msg.topic, attr('reset'), msg.payload,))

    def monitor(self):
        self.client.connect("localhost", 1883, 5)
        self.client.loop_forever()


def usage():
    print('''Usage: {} [-h hostname] [-p port] topic...

Topic can contain the standard MQTT wildcards: single level + for a single
topic segment, or # for all topics below a topic. Examples:
    $SYS/#          all system topics
    frischen/adorf/1/currentposition
    frischen/adorf/+/currentposition
    frischen/adorf/#
'''.format(os.path.basename(__file__)), file=sys.stderr, end='')
    sys.exit(64)


def main():
    global config

    try:
        options, remainder = getopt.getopt(
            sys.argv[1:], 'h:p:t?', ['host', 'port', help])
    except getopt.GetoptError as e:
        print('Error parsing command line: {}'.format(e), file=sys.stderr)
        usage()

    for opt, arg in options:
        if opt in ('-h', '--host'):
            config['host'] = arg
        if opt in ('-p', '--port'):
            config['port'] = arg
        if opt in ('-t', '--timestamp'):
            config['timestamp'] = True
        if opt in ('-?', '--help'):
            usage()

    if len(remainder) < 1:
        print('You need to specify at least one topic.', file=sys.stderr)
        usage()

    m = MqttMonitor(config, remainder)
    m.monitor()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
