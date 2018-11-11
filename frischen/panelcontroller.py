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
        self.__value = 0
        self.task = None
        if self.kind not in self.controller.elements:
            self.controller.elementClass[self.kind] = self.__class__
            self.controller.elements[self.kind] = {}
        self.controller.elements[self.kind][self.name] = self

    @classmethod
    def all(cls, controller):
        kind = cls.__name__.lower()
        return controller.elements[kind].values()

    @classmethod
    def initialize_all(cls, controller):
        for e in cls.all(controller):
            e.initialize()

    def initialize(self):
        self.value = self.initial_value

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

    def on_button(self, controller):
        pass


class BlockEnd(Element):
    def on_button(self, controller, value):
        if value and controller.is_outer_button('BlGT'):
            self.value = 1


class Signal(Element):
    initial_value = 'Hp0'

    def on_button(self, controller, value):
        self.button = value
        if value:
            if controller.is_outer_button('SGT'):
                self.start_change_shunting()
                return
            if controller.is_outer_button('HaGT'):
                self.start_halt()
                return
            if controller.is_outer_button('ErsGT'):
                self.start_alt()
                return
            if controller.is_outer_button('FHT'):
                for route in controller.routes.values():
                    if route.s1 == self and route.locked:
                        route.unlock()
                return

            pushed = []
            for e in self.all(controller):
                if e.button:
                    pushed.append(e)
            if len(pushed) == 2:
                route = f'{pushed[0].name},{pushed[1].name}'
                if route in controller.routes:
                    controller.routes[route].start()
                else:
                    route = f'{pushed[1].name},{pushed[0].name}'
                    if route in controller.routes:
                        controller.routes[route].start()

    def __init__(self, controller, name):
        super().__init__(controller, name)
        self.__value = 'Hp0'
        self.aspects = []
        self.button = 0

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

    def start_home(self, aspect):
        self.value = aspect


class Track(Element):
    initial_value = (0, 0)

    def __init__(self, controller, name):
        super().__init__(controller, name)
        self.locked = 0
        self.occupied = 0

    @property
    def value(self):
        v = ','.join([str(i) for i in [self.locked, self.occupied]])
        return v

    @value.setter
    def value(self, value):
        (self.locked, self.occupied) = value
        self.publish()

    def set_locked(self, locked):
        self.locked = locked
        self.publish()

    def set_blocked(self, occupied):
        self.occupied = occupied
        self.publish()


class Turnout(Element):
    initial_value = (0, 0, 0, 0)

    def on_button(self, controller, value):
        if value and controller.is_outer_button('WGT') \
                and not self.locked and not self.blocked \
                and not self.occupied:
            self.start_change()

    def __init__(self, controller, name):
        super().__init__(controller, name)
        self.position = 0
        self.moving = 0
        self.locked = 0
        self.blocked = 0
        self.occupied = 0
        self.task = None

    def initialize(self):
        self.position = 1
        self.start_change(0)

    @property
    def value(self):
        v = ','.join([str(i) for i in [self.position, self.moving, self.locked, self.blocked]])
        return v

    @value.setter
    def value(self, value):
        (self.position, self.moving, self.locked, self.blocked) = value
        self.publish()

    def set_position(self, position):
        self.position = position
        self.publish()

    def set_moving(self, moving):
        self.moving = moving
        self.publish()

    def set_locked(self, locked):
        self.locked = locked
        self.publish()

    def set_blocked(self, blocked):
        self.blocked = blocked
        self.publish()

    def start_change(self, position=None):
        if position is None:
            position = 1 if self.position == 0 else 0
        if self.task:
            self.task.cancel()
        self.task = asyncio.create_task(self.change(position))
        return self.task

    async def change(self, position):
        if position == self.position:
            return
        self.position = position
        self.moving = 1
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


class Route():
    def __init__(self, controller, s1, s2):
        self.s1 = controller.get(Signal, s1)
        self.s2 = controller.get(Signal, s2)
        self.name = f'{self.s1.name},{self.s2.name}'
        self.locked = False
        self.tracks = []
        self.turnouts = []
        self.flankProtections = []
        self.controller = controller
        self.controller.routes[self.name] = self

    def __repr__(self):
        return f'{self.__class__.__name__}<{self.name}>'

    def turnout(self, turnout, position):
        turnout = self.controller.get(Turnout, turnout)
        self.turnouts.append((turnout, position))
        self.tracks.append(turnout)
        return self

    def flankProtection(self, turnout, position):
        turnout = self.controller.get(Turnout, turnout)
        self.flankProtections.append((turnout, position))
        return self

    def track(self, track):
        track = self.controller.get(Track, track)
        self.tracks.append(track)
        return self

    def start(self):
        logger.debug(f'started: {self}')
        asyncio.create_task(self.change())

    async def change(self):
        tasks = []
        for (turnout, position) in self.turnouts:
            tasks.append(turnout.start_change(position))
        for (turnout, position) in self.flankProtections:
            tasks.append(turnout.start_change(position))
        await asyncio.wait(tasks)
        for (turnout, position) in self.turnouts:
            turnout.set_locked(1)
        for (turnout, position) in self.flankProtections:
            turnout.set_locked(1)
        for track in self.tracks:
            if track.occupied:
                logger.debug(f'Track {track} is occupied, not activating route {self}')
                return
        for track in self.tracks:
            track.set_locked(1)
        self.s1.start_home('Hp1')
        self.locked = True

    def unlock(self):
        self.s1.start_home('Hp0')
        for (turnout, position) in self.turnouts:
            turnout.set_locked(0)
        for (turnout, position) in self.flankProtections:
            turnout.set_locked(0)
        for track in self.tracks:
            track.set_locked(0)


class Controller():
    def __init__(self, base_topic):
        self.client = MQTTClient()
        self.connected = False
        self.elementClass = {}
        self.elements = {}
        self.outer_buttons = {}
        self.base_topic = base_topic
        self.routes = {}
        OuterButton(self, 'BlGT')
        OuterButton(self, 'ErsGT')
        OuterButton(self, 'FHT')
        OuterButton(self, 'HaGT')
        OuterButton(self, 'SGT')
        OuterButton(self, 'WGT')
        logger.setLevel(logging.DEBUG)

    async def connect(self):
        await self.client.connect('mqtt://localhost/')

    def get(self, cls, name):
        clsname = cls.__name__.lower()
        return self.elements[clsname][name]

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

    async def handle(self):
        self.connected = True
        for cls in self.elementClass.values():
            cls.initialize_all(self)
        await self.client.subscribe([
            (self.topic('button', '#'), QOS_0)])
        try:
            while self.connected:
                message = await self.client.deliver_message()
                packet = message.publish_packet
                topic = packet.variable_header.topic_name
                value = packet.payload.data.decode()

                button = self.subject(topic, 'button')
                value = int(value)

                if button in self.outer_buttons:
                    self.outer_buttons[button].state = value
                else:
                    for elementClassname in self.elements.keys():
                        for b in self.elements[elementClassname].values():
                            if (b.name == button):
                                b.on_button(self, value)

            await self.client.unsubscribe(['frischen/time/#'])
            await self.client.disconnect()
        except ClientException as ce:
            logger.error(f"Client exception: {ce}")
