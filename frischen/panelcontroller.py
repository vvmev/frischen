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
        self.controller.publish(
            self.controller.topic('switch', self.name),
            f'{self.position},{self.moving}'.encode('utf-8')
        )

    def set(self, position, moving):
        self.position = position
        self.moving = moving
        self.publish()

    async def change(self):
        if self.moving == 1:
            return
        self.moving = 1
        self.position = 1 if self.position == 0 else 0
        self.publish()

        await asyncio.sleep(6)
        self.moving = 0
        self.publish()


class SwitchController():
    def __init__(self, base_topic):
        self.client = MQTTClient()
        self.switch_group_button = 'WGT'
        self.switch_group_button_state = 0
        self.switch_group_button_reset = None
        self.switches = {}
        self.base_topic = base_topic
        logger.setLevel(logging.DEBUG)

    async def connect(self):
        await self.client.connect('mqtt://localhost/')

    def topic(self, kind, subject):
        return f'{self.base_topic}/{kind}/{subject}'

    def subject(self, topic, kind):
        base = f'{self.base_topic}/{kind}'
        i = topic.find(base)
        return topic[len(base)+1:] if i == 0 else None

    def publish(self, topic, value):
        """
        Publish a message and don't wait, "fire and forget" style.
        """
        logger.debug(f'Publishing {topic} = {value}')
        asyncio.create_task(self.client.publish(topic, value))

    async def reset_signal_group_button(self):
        logger.debug(f'Started signal_group_button timeout')
        await asyncio.sleep(5)
        logger.debug(f'signal_group_button timeout reached')
        self.switch_group_button_state = 0
        self.publish(
            self.topic('button', self.switch_group_button), b'0')
        self.switch_group_button_reset = None

    def start_reset_signal_group_button(self):
        if self.switch_group_button_reset:
            self.switch_group_button_reset.cancel()
        self.switch_group_button_reset = asyncio.create_task(
            self.reset_signal_group_button())

    async def handle(self):
        self.publish(
            self.topic('button', self.switch_group_button), b'0')
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
                value = int(value)
                if button == self.switch_group_button:
                    self.switch_group_button_state = value
                    if value == 1:
                        self.start_reset_signal_group_button()
                if button in self.switches:
                    if self.switch_group_button_state == 1 and \
                            value == 1:
                        self.start_reset_signal_group_button()
                        asyncio.ensure_future(self.switches[button].change())
            await self.client.unsubscribe(['frischen/time/#'])
            await self.client.disconnect()
        except ClientException as ce:
            logger.error(f"Client exception: {ce}")
