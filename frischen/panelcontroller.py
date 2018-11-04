import asyncio
import logging

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_0


logger = logging.getLogger(__name__)


class Switch():
    def __init__(self, controller, name):
        self.controller = controller
        self.name = name
        self.position = 0
        self.moving = 0

    def __repr__(self):
        return f'Switch<{self.name}>'

    def publish(self):
        c = self.controller
        return c.client.publish(
            f'{c.base_topic}/switch/{self.name}',
            f'{self.position},{self.moving}'.encode('utf-8')
        )

    def set(self, position, moving):
        self.position = position
        self.moving = moving
        return asyncio.ensure_future(self.publish())

    async def change(self):
        if self.moving == 1:
            return
        self.moving = 1
        self.position = 1 if self.position == 0 else 0
        await self.publish()
        await asyncio.sleep(6)
        self.moving = 0
        await self.publish()


class SwitchController():
    def __init__(self, base_topic):
        self.client = MQTTClient()
        self.switch_group_button = 'WGT'
        self.switch_group_button_state = '0'
        self.switches = {}
        self.base_topic = base_topic

    async def connect(self):
        await self.client.connect('mqtt://localhost/')

    def topic(self, kind, subject):
        return f'{self.base_topic}/{kind}/{subject}'

    def subject(self, topic, kind):
        base = f'{self.base_topic}/{kind}'
        i = topic.find(base)
        return topic[len(base)+1:] if i == 0 else None

    async def handle(self):
        for s in self.switches.values():
            s.set(0, 0)
        await self.client.subscribe([
            (self.topic('button', '#'), QOS_0)])
        try:
            while True:
                message = await self.client.deliver_message()
                packet = message.publish_packet
                topic = packet.variable_header.topic_name
                value = packet.payload.data.decode()

                button = self.subject(topic, 'button')
                if button == self.switch_group_button:
                    self.switch_group_button_state = value
                if button in self.switches:
                    if self.switch_group_button_state == '1' and \
                            value == '1':
                        asyncio.ensure_future(self.switches[button].change())
            await self.client.unsubscribe(['frischen/time/#'])
            await self.client.disconnect()
        except ClientException as ce:
            logger.error(f"Client exception: {ce}")
