import asyncio
import logging

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_0


logger = logging.getLogger(__name__)


class Element():
    initial_value = 0

    def __init__(self, controller, name):
        self.controller = controller
        self.kind = self.__class__.__name__.lower()
        self.name = name
        self.state = 0
        self.task = None
        if self.kind not in self.controller.elements:
            logger.debug(f'my name is {self.kind}')
            self.controller.elementClass[self.kind] = self.__class__
            self.controller.elements[self.kind] = {}
        self.controller.elements[self.kind][self.name] = self

    @classmethod
    def initialize(cls, controller):
        kind = cls.__name__.lower()
        for e in controller.elements[kind].values():
            e.value = cls.initial_value

    @classmethod
    def act_on_button(cls, controller, button, value):
        if value and button in controller.elements['blockend'] \
                and controller.is_outer_button('BlGT'):
            controller.elements['blockend'][button].value = 1

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, value):
        self.__value = value
        self.publish()

    def __repr__(self):
        return f'{self.__class__.__name__}<{self.name}>'

    def publish(self):
        logger.debug(f'{self}.publish({self.kind}, {self.value})')
        self.controller.publish(
            self.controller.topic(self.kind, self.name),
            str(self.value).encode('utf-8'))


class BlockEnd(Element):
    pass


class Signal(Element):
    initial_value = 'Hp0'

    @classmethod
    def act_on_button(cls, controller, button, value):
        if value and button in controller.elements['signal']:
            if controller.is_outer_button('SGT'):
                controller.elements['signal'][button].start_change_shunting()
            if controller.is_outer_button('HaGT'):
                controller.elements['signal'][button].start_halt()
            if controller.is_outer_button('ErsGT'):
                controller.elements['signal'][button].start_alt()

    def __init__(self, controller, name):
        super().__init__(controller, name)
        self.value = 'Hp0'
        self.aspects = []

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

    def start_alt(self):
        if 'Zs1' in self.aspects and self.value == 'Hp0':
            if self.task:
                self.task.cancel()
            self.task = asyncio.create_task(self.change_alt())

    async def change_alt(self):
        self.value = 'Zs1'
        await asyncio.sleep(15)
        self.value = 'Hp0'

    def start_halt(self):
        if self.task:
            self.task.cancel()
        if self.value != 'Hp0':
            self.value = 'Hp0'

    def start_change_shunting(self):
        if 'Sh1' in self.aspects:
            if self.value == 'Hp0':
                self.value = 'Sh1'


class Switch(Element):
    initial_value = (0, 0)

    @classmethod
    def act_on_button(cls, controller, button, value):
        if value and button in controller.elements['switch'] \
                and controller.is_outer_button('WGT'):
            controller.elements['switch'][button].start_change()

    def __init__(self, controller, name):
        super().__init__(controller, name)
        self.position = 0
        self.moving = 0

    @property
    def value(self):
        return f'{self.position},{self.moving}'

    @value.setter
    def value(self, value):
        self.position = value[0]
        self.moving = value[1]
        self.publish()

    def start_change(self):
        if self.moving:
            return
        asyncio.create_task(self.change())

    async def change(self):
        if self.moving == 1:
            return
        self.moving = 1
        self.position = 1 if self.position == 0 else 0
        self.publish()

        await asyncio.sleep(6)
        self.moving = 0
        self.publish()


class OuterButton():
    def __init__(self, controller, name):
        self.controller = controller
        self.name = name
        self.task = None
        self.state = 0
        self.task = None
        self.controller.outer_buttons[self.name] = self

    def __repr__(self):
        return f'OuterButton<{self.name}>'


class Controller():
    def __init__(self, base_topic):
        self.client = MQTTClient()
        self.connected = False
        self.elementClass = {}
        self.elements = {}
        self.outer_buttons = {}
        self.base_topic = base_topic
        OuterButton(self, 'BlGT')
        OuterButton(self, 'ErsGT')
        OuterButton(self, 'HaGT')
        OuterButton(self, 'SGT')
        OuterButton(self, 'WGT')
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
        if not self.connected:
            return
        logger.debug(f'Publishing {topic} = {value}')
        asyncio.create_task(self.client.publish(topic, value))

    def is_outer_button(self, button):
        """
        Return true only if this outer button is pushed, but no other.
        """
        if not self.outer_buttons[button].state:
            return False
        for b in self.outer_buttons.values():
            if b.state and b.name != button:
                return False
        return True

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
        self.connected = True
        for cls in self.elementClass.values():
            cls.initialize(self)
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

                if button in self.outer_buttons:
                    self.outer_buttons[button].state = value

                for cls in self.elementClass.values():
                    cls.act_on_button(self, button, value)

            await self.client.unsubscribe(['frischen/time/#'])
            await self.client.disconnect()
        except ClientException as ce:
            logger.error(f"Client exception: {ce}")
