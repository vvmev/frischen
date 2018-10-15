#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from datetime import datetime

from colored import attr, fg

import paho.mqtt.client as mqtt


class MqttClient:
    qos = {
        0: 'M',  # at most once
        1: 'L',  # at least once
        2: 'E',  # exactly once
    }

    def __init__(self, client_id, host='localhost', port=1883):
        self.client_id = client_id
        self.host = host
        self.port = port
        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_log = self.on_log
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        self.client.on_subscribe = self.on_subscribe
        self.client.on_subscribe = self.on_subscribe
        self.client.on_unsubscribe = self.on_unsubscribe
        self.connected = False

    def on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            print('Unable to connect to broker {}:{}: {}'.format(
                self.host, self.port, rc))
            sys.exit(64)
        self.connected = True
        pass

    def on_disconnect(self, client, userdata, rc):
        self.connected = False
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
    def __init__(self, client_id, topics=[], host='localhost', port=1883,
                 timestamp=True):
        super().__init__(client_id, host, port)
        self.timestamp = timestamp
        if not isinstance(topics, list):
            raise TypeError('topcis must be a list')
        if len(topics) == 0:
            raise ValueError('must specify at least one topic')
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

    def __init__(self, client_id, host='localhost', port=1883):
        super().__init__(client_id, host, port)
        self.complete = False

    def publish_next(self):
        if len(self.messages) == 0:
            self.complete = True
        else:
            self.client.publish(self.topic, self.messages.pop(0))

    def on_connect(self, client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)
        self.publish_next()

    def on_publish(self, client, userdata, mid):
        super().on_publish(client, userdata, mid)
        self.publish_next()

    def post(self, topic, messages):
        self.topic = topic
        self.messages = messages
        self.complete = False
        if not isinstance(messages, list):
            raise TypeError('messages must be a list')
        if self.connected:
            self.publish_next()
        else:
            self.client.connect(self.host, self.port, 5)
        while not self.complete:
            self.client.loop(0.01)
