import asyncio
import logging

from inspect import isclass

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_2


logger = logging.getLogger(__name__)


def to_bool(v):
    """Returns True if value represents a true-ish value."""
    return v in [1, True, '1', 't', 'T', 'true', 'True', 'y', 'yes']


def array_to_str(ary):
    """Return a string representing the array."""
    r = []
    for i in ary:
        if isinstance(i, bool):
            r.append('{:b}'.format(i))
        else:
            r.append(str(i))
    return ','.join(r)


class PubSubTopic():
    """A simple way for one object to notify others."""
    def __init__(self):
        self.subscribers = []

    def subscribe(self, name, fn):
        """Register callback to be called when publish() is called."""
        self.subscribers.append((name, fn))

    def publish(self, *args, **kwargs):
        """Call all registered subscribers."""
        for name, fn in self.subscribers:
            logger.debug(f'post {name} {args}')
            fn(*args, **kwargs)


class MQTTDispatcher():
    """Subscribe to one or more MQTT topics, and call the registered callbacks with the messages received."""

    def __init__(self, client):
        self.client = client
        self.subscribers = {}
        self.connected = True

    def subscribe(self, topic, name, fn):
        """Subscribe a callback function to a topic."""
        if topic not in self.subscribers:
            self.subscribers[topic] = PubSubTopic()
        self.subscribers[topic].subscribe(name, fn)

    def dispatch_one(self, topic, value):
        """Dispatch one message to all subscribers."""
        if topic in self.subscribers:
            self.subscribers[topic].publish(topic, value)

    async def dispatch(self):
        """Receive and dispatch messages until told to stop."""
        await self.client.subscribe([(t, QOS_2) for t in self.subscribers.keys()])

        while self.connected:
            message = await self.client.deliver_message()
            packet = message.publish_packet
            topic = packet.variable_header.topic_name
            value = packet.payload.data.decode()
            self.dispatch_one(topic, value)

        await self.client.unsubscribe(self.subscribers.keys())


class ElementManager():
    """Manage the collection of elements created from a class."""

    def __init__(self):
        self.objects = {}

    def all(self):
        """Return all registered elements."""
        return self.objects.values()

    def get(self, name):
        if isinstance(name, str):
            return self.objects.get(name)
        if name in self.objects.values():
            return name
        return None

    def entries(self):
        return self.objects

    def register(self, element):
        """Register an element with this manager."""
        self.objects[element.name] = element

    def reset_all(self):
        """
        Bring all objects to a defined state.

        By calling each element's reset() method, all properties are reset, and the element's state is published."""
        for e in self.all():
            e.reset()

    def unregister(self, element):
        """
        Remove element from the manager.

        The element to be removed can be specified by the object or its name.
        """
        if element in self.objects:
            del self.objects[element]
        if 'name' in element:
            del self.objects[element.name]


class Element():
    """The base class for elements of the signal tower.

    There is one state variable, occupied, which shows whether the track represented by this element is currently
    occupied by a train.

    This is an abstract base class.
    """

    objects = ElementManager()

    def __init__(self, tower, name):
        self.kind = self.__class__.__name__.lower()
        self.name = name
        self.objects.register(self)
        self.tower = tower
        self.pushed = False
        self.task = None
        self.properties = ['occupied']
        self.on_update = PubSubTopic()
        self.tower.dispatcher.subscribe(self.tower.panel_topic('button', self.name), str(self), self.on_button)
        self.tower.dispatcher.subscribe(self.tower.trackside_topic('track', name), str(self), self.on_occupied)

    def __repr__(self):
        return f'{self.__class__.__name__}<{self.name}>'

    def on_button(self, topic, value):
        self.pushed = to_bool(value)

    def on_occupied(self, topic, value):
        self.update(occupied=to_bool(value))

    def publish(self):
        self.tower.publish(self.topic(), self.value.encode('utf-8'))
        self.on_update.publish(self.value)

    def reset(self):
        self.occupied = False
        self.publish()

    def topic(self):
        return self.tower.panel_topic(self.kind, self.name)

    def update(self, **kwargs):
        for k, v in kwargs.items():
            if k not in self.properties:
                raise KeyError(f'property "{k}" is not valid for {self.__class__.__name__}')
            self.__dict__[k] = v
        self.publish()

    @property
    def value(self):
        return array_to_str([self.__dict__[k] for k in self.properties])


class BlockEnd(Element):
    """
    The line block apparatus at the end of line.

    This element has two state variables, on top of the general occupied status:
    * blocked: if True, the block is locked, and no train must enter
    * clearance_lock: if True, the train has not yet gone past the block signal, and the block cannot be unlocked.
    """

    objects = ElementManager()

    def __init__(self, tower, name, blockstart_topic, clearance_lock_release_topic):
        super().__init__(tower, name)
        self.properties += ('blocked', 'clearance_lock')
        self.blocked = False
        self.clearance_lock = True
        if not '/' in blockstart_topic:
            blockstart_topic = self.tower.trackside_topic('block', blockstart_topic)
        if not '/' in clearance_lock_release_topic:
            clearance_lock_release_topic = self.tower.trackside_topic('track', clearance_lock_release_topic)
        self.tower.dispatcher.subscribe(clearance_lock_release_topic, str(self), self.on_clearance_lock_release)
        self.tower.dispatcher.subscribe(blockstart_topic, str(self), self.on_block_start)

    def on_block_start(self, topic, value):
        """The start of the line has locked the block."""
        value = to_bool(value)
        if value:
            self.update(blocked=True)

    def on_button(self, topic, value):
        """The signalman has pushed the button."""
        super().on_button(topic, value)
        if self.pushed and self.tower.is_outer_button('BlGT') \
                and not self.clearance_lock:
            self.update(blocked=False, clearance_lock=True)

    def on_clearance_lock_release(self, topic, value):
        """If the track segment has transitioned from occupied to unoccupied, the clearance lock is unlocked."""
        value = to_bool(value)
        if not value and self.clearance_lock:
            self.update(clearance_lock=False)

    def reset(self):
        self.blocked = False
        self.clearance_lock = True
        super().reset()


class BlockStart(Element):
    """The line block apparatus at the beginning of the line.

    The block is locked when the train occupies this track segment, and unlocked when the remote block end unlocks it.
    """

    objects = ElementManager()

    def __init__(self, tower, name, blockend_topic, blocking_track_topic):
        super().__init__(tower, name)
        self.properties += ('blocked',)
        self.blocked = False
        if not '/' in blockend_topic:
            blockend_topic = self.tower.trackside_topic('block', blockend_topic)
        if not '/' in blocking_track_topic:
            blocking_track_topic = self.tower.trackside_topic('track', blocking_track_topic)
        self.tower.dispatcher.subscribe(blockend_topic, str(self), self.on_blockend)
        self.tower.dispatcher.subscribe(blocking_track_topic, str(self), self.on_blocking_track)

    def on_blockend(self, topic, value):
        """Block apparatus at the end of the block has been unblocked."""
        if not to_bool(value):
            self.update(blocked=False)

    def on_blocking_track(self, topic, value):
        """Track at the beginning of the block has been occupied and clear again."""
        if not to_bool(value):
            self.update(blocked=True)

    def reset(self):
        self.blocked = False
        super().reset()


class Counter(Element):
    """Counts relevant operations on the panel."""

    objects = ElementManager()

    def __init__(self, tower, name, button=None):
        super().__init__(tower, name)
        self.count = 0
        self.properties = ['count']
        if button is None:
            button = OuterButton.objects.get(name)
        if button is None:
            raise KeyError(f'There is no button {name}')
        button.counter = self

    def increment(self):
        """Register a substitute procedure operation."""
        self.count += 1
        self.publish()

    def reset(self):
        self.count = 0
        super().reset()


class DistantSignal(Element):
    """Controls the distant signal based on the aspect of one or more home signals.

    Since the distant signal can indicate the aspect of different home signals, based on the position of one or more
    turnouts, a some logic is implemented to be able to configure these conditions.

    Additionally, if the distant signal is mounted to the same mast as a home signal, the distant signal will be
    switched off if the home signal is showing a stop aspect.
    """

    objects = ElementManager()

    translated_aspects = { 'Hp0': 'Vr0', 'Hp1': 'Vr1', 'Hp2': 'Vr2' }

    def __init__(self, tower, name, home, mounted_at=None):
        super().__init__(tower, name)
        self.mounted_at = None
        self.aspect = 'Vr0'
        self.properties = ['aspect']
        if mounted_at is not None:
            self.mounted_at = Signal.objects.get(mounted_at)
            self.mounted_at.on_update.subscribe('mounted_at', self.mounted_at_changed)
        if isinstance(home, str):
            signal = Signal.objects.get(home)
            signal.on_update.subscribe(f'{self}', lambda aspect: self.start_distant(aspect))
        if isinstance(home, dict):
            k = next(iter(home))
            turnout = Turnout.objects.get(k)
            signals = [Signal.objects.get(s) for s in home[k]]
            signals[0].on_update.subscribe(
                f'{self}',
                lambda aspect:
                self.start_distant(aspect) if turnout.position==0 else False)
            signals[1].on_update.subscribe(
                f'{self}',
                lambda aspect:
                self.start_distant(aspect) if turnout.position==1 else False)

    def topic(self):
        return self.tower.panel_topic('signal', self.name)

    def publish(self):
        if self.mounted_at is not None and self.mounted_at.value == 'Hp0':
            self.tower.publish(self.topic(), '-'.encode('utf-8'))
        else:
            super().publish()

    def start_distant(self, aspect):
        if aspect in self.translated_aspects:
            aspect = self.translated_aspects[aspect]
        self.update(aspect=aspect)

    def mounted_at_changed(self, aspect):
        self.publish()


class Signal(Element):
    """Controls a home signal."""

    objects = ElementManager()

    def __init__(self, tower, name):
        super().__init__(tower, name)
        self.alt_delay = 15
        self.aspect = 'Hp0'
        self.properties = ['aspect']
        self.aspects = []

    def on_button(self, topic, value):
        super().on_button(topic, value)
        if self.pushed:
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
                for route in Route.objects.all():
                    if route.s1 == self and route.locked:
                        Counter.objects.get('FHT').increment()
                        route.unlock()
                        return
                return

            pushed = []
            for e in self.objects.all():
                if e.pushed:
                    pushed.append(e)
            if len(pushed) == 2:
                route = Route.objects.find_by_signals(pushed)
                if route:
                    route.start()

    def add_alt(self):
        self.aspects += ['Zs1']
        return self

    def add_home(self):
        self.aspects += ['Hp0', 'Hp1', 'Hp2']
        return self

    def add_shunting(self):
        self.aspects += ['Sh1']
        return self

    def start_alt(self):
        if 'Zs1' in self.aspects and self.aspect == 'Hp0':
            if self.task:
                self.task.cancel()
            self.task = asyncio.create_task(self.change_alt())
            Counter.objects.get('ErsGT').increment()
        else:
            logger.debug(f'Not activating Zs1: {self.value}')

    async def change_alt(self):
        self.update(aspect='Zs1')
        await asyncio.sleep(self.alt_delay)
        self.update(aspect='Hp0')

    def start_halt(self):
        if self.task:
            self.task.cancel()
        if self.aspect != 'Hp0':
            self.update(aspect='Hp0')

    def start_change_shunting(self):
        if 'Sh1' in self.aspects:
            if self.aspect == 'Hp0':
                self.update(aspect='Sh1')

    def start_home(self, aspect):
        self.update(aspect=aspect)


class Track(Element):
    """Manages a segment of track."""

    objects = ElementManager()

    def __init__(self, tower, name):
        super().__init__(tower, name)
        self.locked = False
        self.properties += ['locked']


class Turnout(Element):
    """Manages a turnout."""

    objects = ElementManager()

    def __init__(self, tower, name):
        super().__init__(tower, name)
        self.position = False
        self.moving = False
        self.locked = False
        self.blocked = False
        self.properties += ['position', 'moving', 'locked', 'blocked']
        self.moving_delay = 6
        self.task = None

    def reset(self):
        self.position = False
        self.moving = False
        self.locked = False
        self.blocked = False
        super().reset()

    def on_button(self, topic, value):
        super().on_button(topic, value)
        if self.pushed and self.tower.is_outer_button('WGT') \
                and not self.locked and not self.blocked \
                and not self.occupied:
            self.start_change()

    def start_change(self, position=None):
        if position is None:
            position = not self.position
        if self.task:
            self.task.cancel()
        self.task = asyncio.create_task(self.change(position))
        return self.task

    async def change(self, position):
        if position == self.position:
            return
        self.position = position
        self.update(moving=True)

        await asyncio.sleep(self.moving_delay)
        self.update(moving=False)


class OuterButton(Element):
    """Records an outer button."""

    objects = ElementManager()

    def __init__(self, tower, name):
        super().__init__(tower, name)
        self.properties = []
        self.counter = None

    def add_counter(self):
        """Add a counter to this button."""
        self.counter = Counter(self.tower, self.name)
        return self

    def count(self):
        """Increment the counter for this button."""
        if self.counter is not None:
            self.counter.increment()

    def publish(self):
        """No state to publish."""
        pass

    def update(self, **kwargs):
        """No state to update."""
        raise KeyError(f'{self.__class__.__name__} has no updateable properties')


class RouteManager(ElementManager):
    def find_by_signals(self, signals):
        r = self.objects.get(f'{signals[0].name},{signals[1].name}')
        if not r:
            r = self.objects.get(f'{signals[1].name},{signals[0].name}')
        return r


class Route():
    """Manages a route.

    A route connects a starting signal to a destination signal, and locks any intermediate turnouts and switches.
    """

    objects = RouteManager()

    def __init__(self, tower, s1, s2, release_topic):
        self.s1 = Signal.objects.get(s1)
        self.s2 = Signal.objects.get(s2)
        self.name = f'{self.s1.name},{self.s2.name}'
        self.locked = False
        self.tracks = []
        self.turnouts = []
        self.flankProtections = []
        self.tower = tower
        self.objects.register(self)
        self.step_delay = 0.2
        if not '/' in release_topic:
            release_topic = self.tower.trackside_topic('track', release_topic)
        self.tower.dispatcher.subscribe(release_topic, str(self), self.on_release)

    def __repr__(self):
        return f'{self.__class__.__name__}<{self.name}>'

    def reset(self):
        pass

    def add_turnout(self, turnout, position):
        turnout = Turnout.objects.get(turnout)
        self.turnouts.append((turnout, position))
        self.tracks.append(turnout)
        return self

    def add_flank_protection(self, turnout, position):
        turnout = Turnout.objects.get(turnout)
        self.flankProtections.append((turnout, position))
        return self

    def add_track(self, track):
        track = Track.objects.get(track)
        self.tracks.append(track)
        return self

    def on_release(self, topic, value):
        """If the track segment has transitioned from occupied to unoccupied, the clearance lock is unlocked."""
        value = to_bool(value)
        if not value:
            self.unlock()

    def start(self):
        logger.debug(f'started: {self}')
        return asyncio.create_task(self.change())

    async def change(self):
        tasks = []
        for (turnout, position) in self.turnouts + self.flankProtections:
            if turnout.locked:
                logger.debug(f'Turnout {turnout} is already locked, not activating route {self}')
                return
            if turnout.occupied:
                logger.debug(f'Turnout {turnout} is occupied, not activating route {self}')
                return
        for (turnout, position) in self.turnouts + self.flankProtections:
            tasks.append(turnout.start_change(position))
            await asyncio.sleep(self.step_delay)
        await asyncio.wait(tasks)
        for (turnout, position) in self.turnouts + self.flankProtections:
            if turnout.occupied:
                logger.debug(f'Turnout {turnout} is occupied, not activating route {self}')
                return
        for (turnout, position) in self.turnouts + self.flankProtections:
            turnout.update(locked=1)
            await asyncio.sleep(self.step_delay)
        for track in self.tracks:
            if track.occupied:
                logger.debug(f'Track {track} is occupied, not activating route {self}')
                return
        for track in self.tracks:
            track.update(locked=1)
            await asyncio.sleep(self.step_delay)
        self.s1.start_home('Hp1')
        self.locked = True

    def unlock(self):
        self.s1.start_home('Hp0')
        for (turnout, position) in self.turnouts + self.flankProtections:
            turnout.update(locked=0)
        for track in self.tracks:
            track.update(locked=0)
        self.locked = False


class Tower():
    def __init__(self, name, client=None):
        if client is None:
            self.client = MQTTClient()
        else:
            self.client = client
        self.dispatcher = MQTTDispatcher(self.client)
        self.connected = False
        self.name = name
        self.managers = [BlockEnd, BlockStart, Counter, DistantSignal, OuterButton, Route, Signal, Track, Turnout]

        OuterButton(self, 'AsT').add_counter()
        OuterButton(self, 'BlGT')
        OuterButton(self, 'ErsGT').add_counter()
        OuterButton(self, 'FHT').add_counter()
        OuterButton(self, 'HaGT')
        OuterButton(self, 'SGT')
        OuterButton(self, 'WGT')
        OuterButton(self, 'WHT').add_counter()

        logger.setLevel(logging.DEBUG)

    def reset_all(self):
        """Reset all managed elements."""

        for cls in self.managers:
            cls.objects.reset_all()

    def is_outer_button(self, button):
        """Return true only if this outer button is pushed, but no other."""

        buttons = OuterButton.objects.entries()
        if not buttons[button].pushed:
            return False
        for b in buttons.values():
            if b.pushed and b.name != button:
                return False
        return True

    def publish(self, topic, value):
        """Publish a message and don't wait, "fire and forget" style."""

        if not self.connected:
            return
        logger.debug(f'Publishing {topic} = {value.decode("utf-8")}')
        return asyncio.create_task(self.client.publish(topic, value))

    def panel_topic(self, kind, subject):
        """Return the full topic for a panel element."""

        return f'frischen/{self.name}/panel/{kind}/{subject}'

    def trackside_topic(self, kind, subject):
        """Return the full topic for a trackside element."""

        return f'frischen/{self.name}/trackside/{kind}/{subject}'

    async def run(self):
        """Connect to the broker and act on messages received."""
        await self.client.connect('mqtt://localhost/')
        self.connected = True
        self.reset_all()
        await self.dispatcher.dispatch()
        await self.client.disconnect()
