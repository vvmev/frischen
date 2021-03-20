"""
A Spurplan-Drucktasten Lorenz 20 (SpDrL20) signal tower.

The :py:class:`Tower` implements the tower itself, while the
:py:class:`Element` and derived classes implement the control elements of
the tower.

These elements can be added to the tower:

* :py:class:`BlockEnd`
* :py:class:`BlockStart`
* :py:class:`Counter`
* :py:class:`DistantSignal`
* :py:class:`OuterButton`
* :py:class:`Route`
* :py:class:`Signal`
* :py:class:`Track`


Example
^^^^^^^

The following code sets up a tower with some elements.

.. code-block:: Python

    tower = Tower('a_tower')
    Turnout(tower, 'W1')
    Signal(tower, 'A')
    DistantSignal(tower, 'a', 'A')

"""
import asyncio
import logging

from inspect import isclass

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_2


logger = logging.getLogger(__name__)


def to_bool(v):
    """Returns :py:const:`True` if value is ``True``, or any string value
    representing true, such as ``y`` or ``true``.

    :param v: an object to be evaluated
    :returns: boolean
    """
    return v in [1, True, '1', 't', 'T', 'true', 'True', 'y', 'yes']


def array_to_str(ary):
    """Return a string representing the array.

    Each of the arrays values are joined by a comma ``,``. Each value is
    converted to a string, with ``bool`` values converted to ``0`` and ``1``,
    respectively.

    :param ary: The array to be converted
    :returns: The string
    """
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
        """Register callback to be called when publish() is called.

        :param name: A name for this callback; used only for debugging and
            logging.
        :param fn: The callback function to be called on
            :py:func:`PubSubTopic.publish`.
        """
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
        """Subscribe a callback function to a topic.

        :param name: A name for this callback; used only for debugging and
            logging.
        :param fn: The callback function to be called on
            :py:func:`PubSubTopic.publish`.
        """
        if topic not in self.subscribers:
            self.subscribers[topic] = PubSubTopic()
        self.subscribers[topic].subscribe(name, fn)

    def dispatch_one(self, topic, value):
        """Dispatch one message to all subscribers.

        :param topic: the message topic
        :param value: the message content
        """
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
        """Return element by name.

        As a convenience, the object being retrieved can be specified by name
        or by the object itself. When passing in the object, ``None`` will be
        returned if the object is not part of this manager.

        :param name: the name of an object in this manager, or the object
            itself.
        :return: The object or ``None``.
        """
        if isinstance(name, str):
            return self.objects.get(name)
        if name in self.objects.values():
            return name
        return None

    def entries(self):
        """Returns the dict of all objects.

        :return: dict of all objects
        """
        return self.objects

    def register(self, element):
        """Register an element with this manager.

        :param element: The element to be registered."""
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
        :param element: the element to be unregistered.
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
    """The object manager for these elements. See :py:class:`ElementManager`."""

    def __init__(self, tower, name):
        """
        :param tower: The :py:class:`Tower` this element is part of.
        :param name: The name of this element; also used as the topic for the
            panel.
        """
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
        """Returns a string representation of this object."""
        return f'{self.__class__.__name__}<{self.name}>'

    def on_button(self, topic, value):
        """The signalman has pushed the button.

        This callback is invoked when the `name` panel topic receives a
        message.

        :param topic: The topic the message was received under.
        :param value: The contents of the message.
        """
        self.pushed = to_bool(value)

    def on_occupied(self, topic, value):
        """The track occupied status has changed.

        :param topic: The topic the message was received under.
        :param value: The contents of the message.
        """
        self.update(occupied=to_bool(value))

    def publish(self):
        """Publish this elements state to the panel."""
        self.tower.publish(self.topic(), self.value.encode('utf-8'))
        self.on_update.publish(self.value)

    def reset(self):
        """Reset element to initial state and publish."""
        self.occupied = False
        self.publish()

    def topic(self):
        """Returns the full panel topic for this element.

        :return: topic as string.
        """
        return self.tower.panel_topic(self.kind, self.name)

    def update(self, **kwargs):
        """Update this elements properties.

        After updating the properties, publish the new state to the panel.

        :param kwargs: you can specify one or more properties as named
            parameters.
        """
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

    * ``blocked``: if True, the block is locked, and no train must enter.
    * ``clearance_lock``: if True, the train has not yet gone past the block
        signal, and the block cannot be unlocked.

    """

    objects = ElementManager()
    """The object manager for these elements. See :py:class:`ElementManager`."""

    def __init__(self, tower, name, blockstart_topic, clearance_lock_release_topic):
        """Create BlockEnd element.

        :param tower: The :py:class:`Tower` this element is part of.
        :param name: The name of this element; also used as the topic for the
            panel.
        :param blockstart_topic: The trackside topic this element subscribes to
            to learn of the block being locked.
        :param clearance_lock_release_topic: The trackside topic for the rail
            contact or other mechanism that unlocks the clearance lock after
            the train has left the block.
        """
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
        """The start of the line has locked the block.

        This callback is invoked when ``blockstart_topic`` receives a
        message.

        :param topic: The topic the message was received under.
        :param value: The contents of the message.
        """
        value = to_bool(value)
        if value:
            self.update(blocked=True)

    def on_button(self, topic, value):
        """The signalman has pushed the button.

        This callback is invoked when the `name` panel topic receives a
        message.

        :param topic: The topic the message was received under.
        :param value: The contents of the message.
        """
        super().on_button(topic, value)
        if self.pushed and self.tower.is_outer_button('BlGT') \
                and not self.clearance_lock:
            self.update(blocked=False, clearance_lock=True)

    def on_clearance_lock_release(self, topic, value):
        """Track has been cleared.

        If the track segment has transitioned from occupied to unoccupied, the
        clearance lock is unlocked. This callback is invoked when the
        `clearance_lock_release_topic` trackside topic receives a
        message.

        :param topic: The topic the message was received under.
        :param value: The contents of the message.
        """
        value = to_bool(value)
        if not value and self.clearance_lock:
            self.update(clearance_lock=False)

    def reset(self):
        """Reset element to initial state and publish."""
        self.blocked = False
        self.clearance_lock = True
        super().reset()


class BlockStart(Element):
    """The line block apparatus at the beginning of the line.

    The block is locked when the train occupies this track segment, and
    unlocked when the remote blockend unlocks it.
    """

    objects = ElementManager()
    """The object manager for these elements. See :py:class:`ElementManager`."""

    def __init__(self, tower, name, blockend_topic, blocking_track_topic):
        """

        :param tower: The :py:class:`Tower` this element is part of.
        :param name: The name of this element; also used as the topic for the
            panel.
        :param blockend_topic: The trackside topic this element publishes to
            to inform the blockend about the block being locked,
            and subscribes to to learn about the remote blockend unlocking
            the block.
        :param blocking_track_topic: The trackside topic for the rail
            contact or other mechanism that locks the block.
        """
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
        """Block apparatus at the end of the block has been unblocked.

        :param topic: The topic the message was received under.
        :param value: The contents of the message.
        """
        if not to_bool(value):
            self.update(blocked=False)

    def on_blocking_track(self, topic, value):
        """Track at the beginning of the block has been cleared again.

        :param topic: The topic the message was received under.
        :param value: The contents of the message.
        """
        if not to_bool(value):
            self.update(blocked=True)
            # TODO: publish block locked

    def reset(self):
        """Reset element to initial state and publish."""
        self.blocked = False
        super().reset()


class Counter(Element):
    """Counts substitute procedure operations on the panel."""

    objects = ElementManager()
    """The object manager for these elements. See :py:class:`ElementManager`."""

    def __init__(self, tower, name, button=None):
        """
        :param tower: The :py:class:`Tower` this element is part of.
        :param name: The name of this element; also used as the topic for the
            panel.
        :param button: The :py:class:`Button` this counter is attached to.
        """
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
        """Reset element to initial state and publish."""
        self.count = 0
        super().reset()


class DistantSignal(Element):
    """A distant signal.

    The distant signal shows an aspect that indicates to the drive the aspect
    of the respective home signal, so the driver can break in time to come to a
    full stop in fron of the home siganl if necessary.

    Since the distant signal can indicate the aspect of different home signals,
    based on the position of one or more turnouts, some logic is implemented to
    be able to configure these conditions.

    Additionally, if the distant signal is mounted to the same mast as another
    home signal, the distant signal will be switched off if the home signal is
    showing a stop aspect.

    1. Single home signal

    If there are no turnouts between this distant signal and its home signal,
    this distant signal simply shows the respective aspect for its home signal.

    Example:
        >>> DistantSignal(tower, 'a', 'A')

    2. Multiple home signals

    If is a turnout between this distant signal and a home signal,
    this distant signal shows the respective aspect of one of these
    home signals based on the position of the intervening switches.  To
    properly describe this setup, you need to pass a dict with the name of the
    switch, and a sub-array of the two home signals.

    For example:
        >>> DistantSignal(tower, 'p1p2', { 'W5', [ 'P1', 'P2' ]})

    In this example, the distant signal ``p1p2`` will show the respective
    aspect for the home signal ``P1`` if the turnout ``W5`` is in the
    straight position, and will show the aspect of ``P2``  if ``W5`` is set to
    diverging.
    """

    objects = ElementManager()
    """The object manager for these elements. See :py:class:`ElementManager`."""

    translated_aspects = { 'Hp0': 'Vr0', 'Hp1': 'Vr1', 'Hp2': 'Vr2' }

    def __init__(self, tower, name, home, mounted_at=None):
        """
        :param tower: The :py:class:`Tower` this element is part of.
        :param name: The name of this element; also used as the topic for the
            panel.
        :param home: A string or dict describing which home signal this
            distant signal shows its aspects for.
        :param mounted_at: A string or :py:class:`Signal` home signal object.
            If specified, this distant signal is mounted on the same mast as
            the home signal.
        """
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
        """Returns the full panel topic for this element.

        :return: topic as string.
        """
        return self.tower.panel_topic('signal', self.name)

    def publish(self):
        """Publishes this signals aspect to the panel."""
        if self.mounted_at is not None and self.mounted_at.value == 'Hp0':
            self.tower.publish(self.topic(), '-'.encode('utf-8'))
        else:
            super().publish()

    def start_distant(self, aspect):
        """Used by the callbacks to set this signals aspect."""
        if aspect in self.translated_aspects:
            aspect = self.translated_aspects[aspect]
        self.update(aspect=aspect)

    def mounted_at_changed(self, aspect):
        """Callback called when the home signal on the same mask changes."""
        self.publish()


class Signal(Element):
    """Controls a signal.

    A  signal can consist of multiple backgrounds added to its mast. Use these
    methods to add the respective signal backgrounds:

    * :py:meth:`Signal.add_alt` adds an alternate signal background (Zs1)
    * :py:meth:`Signal.add_home` adds the home signal background (Hp0, Hp1, Hp2)
    * :py:meth:`Signal.add_shunting` adds the shunting background (Sh1)

    The ``add_*`` methods return the object itself, allowing the use of the
    builder pattern:
    >>> s1 = Signal(tower, 'A').add_alt().add_home()

    Note that a distant signal mounted to the same mast as a home signal is
    created by adding a :py:class:`DistantSignal` and setting it's
    ``mounted_on`` property to the home signal.

    :ivar alt_timeout: time in seconds the alternate aspect will be shown.
    """

    objects = ElementManager()
    """The object manager for these elements. See :py:class:`ElementManager`."""

    def __init__(self, tower, name):
        """
        :param tower: The :py:class:`Tower` this element is part of.
        :param name: The name of this element; also used as the topic for the
            panel.
        """
        super().__init__(tower, name)
        self.alt_delay = 15
        self.aspect = 'Hp0'
        self.properties = ['aspect']
        self.aspects = []

    def on_button(self, topic, value):
        """The signalman has pushed the button.

        This callback is invoked when the `name` panel topic receives a
        message.

        For a signal, pushing the button will only cause an action when
        pushed together with another.

        * When pushed together with another signal button, and a route has
            been defined for this pair, try to lock that route.
        * When pushed together with the ``SGT`` outer button, try to set the
            signal to the shunting aspect (Sh1).
        * When pushed together with the ``ErsGT`` outer button, try to set
            the signal to the alternate aspect (Zs1).
        * When pushed together with the ``HaGT`` outer button, set the signal
            aspect to stop (Hp0).

        :param topic: The topic the message was received under.
        :param value: The contents of the message.
        """
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
        """Add an alternate signal background to this signal.

        :return: self
        """
        self.aspects += ['Zs1']
        return self

    def add_home(self):
        """Add a home background to this signal."""
        self.aspects += ['Hp0', 'Hp1', 'Hp2']
        return self

    def add_shunting(self):
        """Add a shunting background to this signal."""
        self.aspects += ['Sh1']
        return self

    def start_alt(self):
        """Start the change to the alt aspect (Zs1).

        The alternate aspect will extinguish after
        :py:attr:`Signal.alt_timeout`.
        """
        if 'Zs1' in self.aspects and self.aspect == 'Hp0':
            if self.task:
                self.task.cancel()
            self.task = asyncio.create_task(self.change_alt())
            Counter.objects.get('ErsGT').increment()
        else:
            logger.debug(f'Not activating Zs1: {self.value}')

    async def change_alt(self):
        """Change to alt aspect, then return to stop aspect."""
        self.update(aspect='Zs1')
        await asyncio.sleep(self.alt_delay)
        self.update(aspect='Hp0')

    def start_halt(self):
        """Change to stop aspect."""
        if self.task:
            self.task.cancel()
        if self.aspect != 'Hp0':
            self.update(aspect='Hp0')

    def start_change_shunting(self):
        """Change to shunting aspect."""
        if 'Sh1' in self.aspects:
            if self.aspect == 'Hp0':
                self.update(aspect='Sh1')

    def start_home(self, aspect):
        """Change (home) aspect of this signal."""
        self.update(aspect=aspect)


class Track(Element):
    """Manages a segment of track."""

    objects = ElementManager()
    """The object manager for these elements. See :py:class:`ElementManager`."""

    def __init__(self, tower, name):
        """
        :param tower: The :py:class:`Tower` this element is part of.
        :param name: The name of this element; also used as the topic for the
            panel.
        """
        super().__init__(tower, name)
        self.locked = False
        self.properties += ['locked']


class Turnout(Element):
    """Manages a turnout.

    :ivar position: ``True`` if the turnout it set to diverging.
    :ivar moving: ``True`` if the turnout is moving to a new position.
    :ivar locked: ``True`` if the turnout is locked (typically by a
        :py:class:`Route`).
    :ivar blocked: ``True`` if the turnout has been locked individually.
    """

    objects = ElementManager()
    """The object manager for these elements. See :py:class:`ElementManager`."""

    def __init__(self, tower, name):
        """
        :param tower: The :py:class:`Tower` this element is part of.
        :param name: The name of this element; also used as the topic for the
            panel.
        """
        super().__init__(tower, name)
        self.position = False
        self.moving = False
        self.locked = False
        self.blocked = False
        self.properties += ['position', 'moving', 'locked', 'blocked']
        self.moving_delay = 6
        self.task = None

    def reset(self):
        """Reset element to initial state and publish."""
        self.position = False
        self.moving = False
        self.locked = False
        self.blocked = False
        super().reset()

    def on_button(self, topic, value):
        """The signalman has pushed the button.

        This callback is invoked when the `name` panel topic receives a
        message.

        :param topic: The topic the message was received under.
        :param value: The contents of the message.
        """
        super().on_button(topic, value)
        if self.pushed and self.tower.is_outer_button('WGT') \
                and not self.locked and not self.blocked \
                and not self.occupied:
            self.start_change()

    def start_change(self, position=None):
        """Switch turnout to new position.

        :param position: If specified, move turnout to this position,
            If unspecified, move the turnout to the other position.
        """
        if position is None:
            position = not self.position
        if self.task:
            self.task.cancel()
        self.task = asyncio.create_task(self.change(position))
        return self.task

    async def change(self, position):
        """Start the motion and wait for it to complete."""
        if position == self.position:
            return
        self.position = position
        self.update(moving=True)

        # TODO: instead of this timeout, we need to wait for the trackside
        # element to confirm reaching the final position.
        await asyncio.sleep(self.moving_delay)
        self.update(moving=False)


class OuterButton(Element):
    """Records an outer button."""

    objects = ElementManager()
    """The object manager for these elements. See :py:class:`ElementManager`."""

    def __init__(self, tower, name):
        """The signalman has pushed the button.

        This callback is invoked when the `name` panel topic receives a
        message.

        :param tower: The :py:class:`Tower` this element is part of.
        :param name: The name of this element; also used as the topic for the
            panel.
        """
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
        """No-op method.

        There is no state to publish to the panel."""
        pass

    def update(self, **kwargs):
        """No-op method.

        There is no state to change."""
        raise KeyError(f'{self.__class__.__name__} has no updatable properties')


class RouteManager(ElementManager):
    """
    An object manager for :py:class:`Route` objects.
    """
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
    """The object manager for these elements. See :py:class:`ElementManager`."""

    def __init__(self, tower, s1, s2, release_topic):
        """
        :param tower: The :py:class:`Tower` this element is part of.
        :param s1: The signal at the start of the route.
        :param s2: The signal at the end of the route.
        :param release_topic: The trackside topic the route subscribes to to
            release the route.
        """
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
        """Returns a string representation of this object."""
        return f'{self.__class__.__name__}<{self.name}>'

    def reset(self):
        """Reset element to initial state and publish."""
        pass

    def add_turnout(self, turnout, position):
        """Add a turnout to the route.

        :param turnout: The turnout to be added.
        :param position: The position the turnout needs to be in for the
            route to be locked.
        :return: self
        """
        turnout = Turnout.objects.get(turnout)
        self.turnouts.append((turnout, position))
        self.tracks.append(turnout)
        return self

    def add_flank_protection(self, turnout, position):
        """Add a turnout as flank protection.

        :param turnout: The turnout to be added.
        :param position: The position the turnout needs to be in for the
            route to be locked.
        :return: self
        """
        turnout = Turnout.objects.get(turnout)
        self.flankProtections.append((turnout, position))
        return self

    def add_track(self, track):
        """Add a track.

        :param track: The track to be added
        :return: self
        """
        track = Track.objects.get(track)
        self.tracks.append(track)
        return self

    def on_release(self, topic, value):
        """Callback for unlocking the route.

        :param topic: The topic the message was received under.
        :param value: The contents of the message.
        """
        value = to_bool(value)
        if not value:
            self.unlock()

    def start(self):
        """Start locking the route."""
        logger.debug(f'started: {self}')
        return asyncio.create_task(self.change())

    async def change(self):
        """Check and lock route.

        This is the most involved process the tower can perform:

        1. Check that all turnouts are unlocked and unoccupied.

        2. Move all turnouts to their correct positions.

        3. Lock all turnouts.

        4. Check that all tracks are unoccupied.

        5. Lock all tracks.

        6. Set start signal to go aspect.
        """
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
        """Unlock the route.

        If the route is locked, remove locks from turnouts and tracks.
        """
        self.s1.start_home('Hp0')
        for (turnout, position) in self.turnouts + self.flankProtections:
            turnout.update(locked=0)
        for track in self.tracks:
            track.update(locked=0)
        self.locked = False


class Tower():
    """Control logic for a Lorenz 20 signal tower.

    Together with the elements in this module, this class implements the control
    logic. It connects to an operators panel and to trackside equipment
    through MQTT.

    Example:
        >>> tower = Tower('a_station')
        >>> Signal(tower, 'p1p3')
        ... add more elements...
        >>> asyncio.run(tower.run())

    """
    def __init__(self, name, client=None):
        """Set up a new tower.

        :param name: name of tower/station
        :param client: (optional) an existing MQTTClient.
        """
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
