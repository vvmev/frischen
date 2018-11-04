import asyncio
import logging

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_0


logger = logging.getLogger(__name__)


class Signal():
    def __init__(self, controller, name):
        self.controller = controller
        self.name = name
        self.aspect = 'Hp0'
        self.aspects = []

    def __repr__(self):
        return f'Signal<{self.name}>'

    def alt(self):
        self.aspects += ['Zs1']
        return self

    def distant(self):
        self.aspects += ['Vr0', 'Vr1', 'Vr2']
        return self

    def home(self):
        self.aspects += ['Hp0', 'Hp1', 'Hp2']
        return self

    def shunting(self):
        self.aspects += ['Sh1']
        return self

    def publish(self):
        self.controller.publish(
            self.controller.topic('signal', self.name),
            self.aspect.encode('utf-8')
        )

    def set(self, aspect):
        self.aspect = aspect
        self.publish()

    async def change_shunting(self):
        if 'Sh1' in self.aspects:
            if self.aspect == 'Hp0':
                self.aspect = 'Sh1'
            else:
                self.aspect = 'Hp0'
            self.publish()


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
        self.signal_group_button = 'SGT'
        self.signal_group_button_state = 0
        self.signal_group_button_reset = None
        self.signals = {}
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
        self.signal_group_button_state = 0
        self.publish(
            self.topic('button', self.signal_group_button), b'0')
        self.signal_group_button_reset = None

    def start_reset_signal_group_button(self):
        if self.signal_group_button_reset:
            self.signal_group_button_reset.cancel()
        self.signal_group_button_reset = asyncio.create_task(
            self.reset_signal_group_button())

    async def reset_switch_group_button(self):
        logger.debug(f'Started switch_group_button timeout')
        await asyncio.sleep(5)
        logger.debug(f'switch_group_button timeout reached')
        self.switch_group_button_state = 0
        self.publish(
            self.topic('button', self.switch_group_button), b'0')
        self.switch_group_button_reset = None

    def start_reset_switch_group_button(self):
        if self.switch_group_button_reset:
            self.switch_group_button_reset.cancel()
        self.switch_group_button_reset = asyncio.create_task(
            self.reset_switch_group_button())

    async def handle(self):
        self.publish(
            self.topic('button', self.switch_group_button), b'0')
        for s in self.switches.values():
            s.set(0, 0)
        self.publish(
            self.topic('button', self.signal_group_button), b'0')
        for s in self.signals.values():
            s.set('Hp0')
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

                if button == self.signal_group_button:
                    self.signal_group_button_state = value
                    if value == 1:
                        self.start_reset_signal_group_button()

                if button == self.switch_group_button:
                    self.switch_group_button_state = value
                    if value == 1:
                        self.start_reset_switch_group_button()

                if button in self.switches:
                    if self.switch_group_button_state == 1 and \
                            value == 1:
                        self.start_reset_signal_group_button()
                        asyncio.create_task(self.switches[button].change())

                if button in self.signals:
                    if self.signal_group_button_state == 1 and \
                            value == 1:
                        self.start_reset_signal_group_button()
                        asyncio.create_task(
                            self.signals[button].change_shunting())

            await self.client.unsubscribe(['frischen/time/#'])
            await self.client.disconnect()
        except ClientException as ce:
            logger.error(f"Client exception: {ce}")
