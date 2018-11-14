import asyncio
import logging

from inspect import isclass

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_0


logger = logging.getLogger(__name__)


def to_bool(v):
    return v in [1, '1', 't', 'T', 'true', 'True', 'y', 'yes']


class PubSubTopic():
    """A simple way for one object to notify others."""
    def __init__(self):
        self.subscribers = []

    def subscribe(self, name, fn):
        self.subscribers.append((name, fn))

    def publish(self, *args, **kwargs):
        for name, fn in self.subscribers:
            logger.debug(f'post {name} {args}')
            fn(*args, **kwargs)


class ElementManager():
    """
    Manage the collection of objects created from a class.
    """
    def __init__(self):
        self.objects = {}

    def register(self, element):
        self.objects[element.name] = element

    def unregister(self, element):
        if element in self.objects:
            del self.objects[element]
        if 'name' in element:
            del self.objects[element.name]

    def all(self):
        return self.objects.values()

    def initialize_all(self):
        for e in self.all():
            e.initialize()


class ElementValueProperty():
    def __init__(self, label):
        self.label = label

    def __get__(self, instance, owner):
        return instance.__dict__.get(self.label)

    def __set__(self, instance, value):
        instance.__dict__[self.label] = value


class Element():
    objects = ElementManager()

    occupied = ElementValueProperty('occupied')

    def __init__(self, tower, name):
        self.kind = self.__class__.__name__.lower()
        self.name = name
        self.objects.register(self)
        self.tower = tower
        self.pressed = False
        self.task = None

    def set(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v
        self.publish()

    @property
    def value(self):
        return '{:b}'.format(self.occupied)

    def initialize(self):
        self.set(occupied=False)

    def __repr__(self):
        return f'{self.__class__.__name__}<{self.name}>'

    def topic(self):
        return self.tower.topic(self.kind, self.name)

    def publish(self):
        # logger.debug(f'{self}.publish({self.kind}, {self.value})')
        self.tower.publish(self.topic(), self.value.encode('utf-8'))

    def on_button(self, pressed):
        logger.debug(f'Unimplemented on_button() for class {self}')
        pass


class BlockEnd(Element):
    blocked = ElementValueProperty('blocked')

    @Element.property
    def value(self):
        return '{:b},{:b}'.format(self.occupied, self.blocked)

    def initialize(self):
        super().initialize()
        self.set(blocked=False)

    def on_button(self, pressed):
        if pressed and self.tower.is_outer_button('BlGT'):
            self.pressed = True
        else
            self.pressed = False


class BlockStart(Element):
    pass


class Counter(Element):
    def __init__(self, tower, name):
        super().__init__(tower, name)
        if name in tower.outer_buttons:
            tower.outer_buttons[name].counter = self

    def increment(self):
        self.value += 1


class DistantSignal(Element):
    initial_value = 'Vr0'
    aspects = ['Vr0', 'Vr1', 'Vr2']
    translated_aspects = { 'Hp0': 'Vr0', 'Hp1': 'Vr1', 'Hp2': 'Vr2' }

    def __init__(self, tower, name, home, mounted_at=None):
        super().__init__(tower, name)
        self.mounted_at = None
        if mounted_at is not None:
            self.mounted_at = tower.get('signal', mounted_at)
            self.mounted_at.on_change.subscribe('mounted_at', self.mounted_at_changed)
        if isinstance(home, str):
            signal = self.tower.get('signal', home)
            signal.on_change.subscribe(f'{self}', lambda aspect: self.start_distant(aspect))
        if isinstance(home, dict):
            k = next(iter(home))
            turnout = self.tower.get('turnout', k)
            signals = [self.tower.get('signal', s) for s in home[k]]
            signals[0].on_change.subscribe(
                f'{self}',
                lambda aspect:
                self.start_distant(aspect) if turnout.position==0 else False)
            signals[1].on_change.subscribe(
                f'{self}',
                lambda aspect:
                self.start_distant(aspect) if turnout.position==1 else False)

    @Element.value.setter
    def value(self, value):
        if value in self.translated_aspects:
            value = self.translated_aspects[value]
        if not value in self.aspects:
            return
        Element.value.fset(self, value)

    def topic(self):
        return self.tower.topic('signal', self.name)

    def on_button(self, pressed):
        pass

    def publish(self):
        if self.mounted_at is not None and self.mounted_at.value == 'Hp0':
            self.tower.publish(self.topic(), '-'.encode('utf-8'))
        else:
            super().publish()

    def start_distant(self, aspect):
        logger.debug(f'{self}.start_distant({aspect})')
        self.value = aspect

    def mounted_at_changed(self, aspect):
        self.publish()


class Signal(Element):
    initial_value = 'Hp0'

    def __init__(self, tower, name):
        super().__init__(tower, name)
        # self.__value = 'Hp0'
        self.aspects = []
        self.on_change = PubSubTopic()

    @Element.value.setter
    def value(self, value):
        if not value in self.aspects:
            return
        Element.value.fset(self, value)
        self.on_change.publish(value)

    def on_button(self, pressed):
        self.pressed = pressed
        if pressed:
            if self.tower.is_outer_button('SGT'):
                self.start_change_shunting()
                return
            if self.tower.is_outer_button('HaGT'):
                self.start_halt()
                return
            if self.tower.is_outer_button('ErsGT'):
                self.start_alt()
                return
            if self.tower.is_outer_button('FHT'):
                for route in self.tower.routes.values():
                    if route.s1 == self and route.locked:
                        route.unlock()
                return

            pushed = []
            for e in self.all(self.tower):
                if e.pressed:
                    pushed.append(e)
            if len(pushed) == 2:
                route = f'{pushed[0].name},{pushed[1].name}'
                if route in self.tower.routes:
                    self.tower.routes[route].start()
                else:
                    route = f'{pushed[1].name},{pushed[0].name}'
                    if route in self.tower.routes:
                        self.tower.routes[route].start()

    def alt(self):
        self.aspects += ['Zs1']
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
        else:
            logger.debug(f'Not activating Zs1: {self.value}')

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

    def __init__(self, tower, name):
        super().__init__(tower, name)
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

    def on_button(self, pressed):
        # logger.debug(f'{self} => {pressed}')
        if pressed and self.tower.is_outer_button('WGT') \
                and not self.locked and not self.blocked \
                and not self.occupied:
            self.start_change()

    def __init__(self, tower, name):
        super().__init__(tower, name)
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
    def __init__(self, tower, name):
        self.tower = tower
        self.name = name
        self.task = None
        self.pressed = 0
        self.counter = None
        self.task = None
        self.tower.outer_buttons[self.name] = self

    def __repr__(self):
        return f'OuterButton<{self.name}>'

    def set(self, pressed):
        self.pressed = pressed
        if pressed and self.counter is not None:
            self.counter.increment()


class Route():
    def __init__(self, tower, s1, s2):
        self.s1 = tower.get(Signal, s1)
        self.s2 = tower.get(Signal, s2)
        self.name = f'{self.s1.name},{self.s2.name}'
        self.locked = False
        self.tracks = []
        self.turnouts = []
        self.flankProtections = []
        self.tower = tower
        self.tower.routes[self.name] = self

    def __repr__(self):
        return f'{self.__class__.__name__}<{self.name}>'

    def turnout(self, turnout, position):
        turnout = self.tower.get(Turnout, turnout)
        self.turnouts.append((turnout, position))
        self.tracks.append(turnout)
        return self

    def flankProtection(self, turnout, position):
        turnout = self.tower.get(Turnout, turnout)
        self.flankProtections.append((turnout, position))
        return self

    def track(self, track):
        track = self.tower.get(Track, track)
        self.tracks.append(track)
        return self

    def start(self):
        logger.debug(f'started: {self}')
        asyncio.create_task(self.change())

    async def change(self):
        tasks = []
        for (turnout, position) in self.turnouts + self.flankProtections:
            if turnout.locked:
                logger.debug(f'Turnout {turnout} is already locked, not activating route {self}')
                return
        for (turnout, position) in self.turnouts + self.flankProtections:
            tasks.append(turnout.start_change(position))
            await asyncio.sleep(0.5)
        await asyncio.wait(tasks)
        for (turnout, position) in self.turnouts + self.flankProtections:
            turnout.set_locked(1)
            await asyncio.sleep(0.2)
        for track in self.tracks:
            if track.occupied:
                logger.debug(f'Track {track} is occupied, not activating route {self}')
                return
        for track in self.tracks:
            track.set_locked(1)
            await asyncio.sleep(0.2)
        self.s1.start_home('Hp1')
        self.locked = True

    def unlock(self):
        self.s1.start_home('Hp0')
        for (turnout, position) in self.turnouts + self.flankProtections:
            turnout.set_locked(0)
        for track in self.tracks:
            track.set_locked(0)


class Tower():
    def __init__(self, base_topic):
        self.client = MQTTClient()
        self.connected = False
        self.elementClass = {}
        self.elements = {}
        self.outer_buttons = {}
        self.base_topic = base_topic
        self.routes = {}

        self.managers = [Element.objects]
        OuterButton(self, 'AsT')
        Counter(self, 'AsT')
        OuterButton(self, 'BlGT')
        OuterButton(self, 'ErsGT')
        Counter(self, 'ErsGT')
        OuterButton(self, 'FHT')
        Counter(self, 'FHT')
        OuterButton(self, 'HaGT')
        OuterButton(self, 'SGT')
        OuterButton(self, 'WGT')
        OuterButton(self, 'WHT')
        Counter(self, 'WHT')
        logger.setLevel(logging.DEBUG)

    async def connect(self):
        await self.client.connect('mqtt://localhost/')

    def get(self, cls, name):
        if isclass(cls):
            clsname = cls.__name__.lower()
        elif isinstance(cls, str):
            clsname = cls.lower()
        else:
            raise ValueError('must specify a class or a class name string')
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
        logger.debug(f'Publishing {topic} = {value.decode("utf-8")}')
        asyncio.create_task(self.client.publish(topic, value))

    def is_outer_button(self, button):
        """
        Return true only if this outer button is pushed, but no other.
        """
        if not self.outer_buttons[button].pressed:
            return False
        for b in self.outer_buttons.values():
            if b.pressed and b.name != button:
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
                button = self.subject(packet.variable_header.topic_name, 'button')
                pressed = to_bool(packet.payload.data.decode())

                if button in self.outer_buttons:
                    self.outer_buttons[button].set(pressed)
                else:
                    for elementClassname in self.elements.keys():
                        for b in self.elements[elementClassname].values():
                            if (b.name == button):
                                b.on_button(pressed)

            await self.client.unsubscribe(['frischen/time/#'])
            await self.client.disconnect()
        except ClientException as ce:
            logger.error(f"Client exception: {ce}")
