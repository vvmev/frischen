#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getopt
import os
import sys

from datetime import datetime

from colored import attr, fg
import paho.mqtt.client as mqtt

config = {
    'client_id': 'mqttcmd',
    'host': 'localhost',
    'port': 1883,
    'timestamp': True,
}


class MqttClient:
    qos = {
        0: 'M',  # at most once
        1: 'L',  # at least once
        2: 'E',  # exactly once
    }

    def __init__(self, config, cmd):
        self.client_id = config['client_id']
        self.host = config['host']
        self.port = config['port']
        self.timestamp = config['timestamp']
        self.client = mqtt.Client(
            client_id='{}-{}'.format(self.client_id, cmd))
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_log = self.on_log
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        self.client.on_subscribe = self.on_subscribe
        self.client.on_subscribe = self.on_subscribe
        self.client.on_unsubscribe = self.on_unsubscribe

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            print('Unable to connect to broker {}:{}: {}'.format(
                self.host, self.port, rc))
            sys.exit(64)
        self.on_connect(client, userdata, flags, rc)

    def on_connect(self, client, userdata, flags, rc):
        pass

    def on_disconnect(self, client, userdata, rc):
        pass

    def on_message(self, client, userdata, msg):
        pass

    def on_publish(self, client, userdata, mid):
        pass

    def on_subscribe(self, client, userdata, mid, granted_qos):
        pass

    def on_unsubscribe(client, userdata, mid):
        pass

    def on_log(client, userdata, level, buf):
        print(buf)
        pass


class MqttMonitor(MqttClient):
    def __init__(self, config, topics):
        super().__init__(config, 'monitor')
        self.topics = topics

    def on_connect(self, client, userdata, flags, rc):
        for t in self.topics:
            client.subscribe(t)

    def on_message(self, client, userdata, msg):
        if self.timestamp:
            ts = datetime.now().strftime('%H:%M:%S.%f ')
        else:
            ts = ''
        qos = fg('blue') + self.qos[msg.qos] + attr('reset')
        retain = (fg('blue') + 'R' + attr('reset')) if msg.retain else ''
        print('{}{}{}{} ({}{}): {}'.format(
            ts, fg('green'), msg.topic, attr('reset'),
            qos, retain,
            msg.payload.decode(),))

    def monitor(self):
        self.client.connect(self.host, self.port, 5)
        self.client.loop_forever()


class MqttPost(MqttClient):
    '''
    Connect to broker and post one or more messages.
    '''

    def __init__(self, config):
        super().__init__(config, 'post')
        self.complete = False

    def publish_next(self):
        if len(self.messages) == 0:
            self.complete = True
        else:
            self.client.publish(self.topic, self.messages.pop(0))

    def on_connect(self, client, userdata, flags, rc):
        self.publish_next()

    def on_publish(self, client, userdata, mid):
        self.publish_next()

    def post(self, topic, messages):
        self.topic = topic
        self.messages = messages
        self.client.connect(self.host, self.port, 5)
        while not self.complete:
            self.client.loop(0.1)


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
    m = MqttMonitor(config, args)
    m.monitor()


def cmd_post(args):
        if len(args) < 2:
            print('must specify least the topic and one message',
                  file=sys.stderr)
            usage()
        p = MqttPost(config)
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
