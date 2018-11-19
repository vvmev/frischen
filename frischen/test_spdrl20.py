#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import unittest

from unittest.mock import call, create_autospec, MagicMock, Mock, patch

from hbmqtt.client import MQTTClient

from frischen.spdrl20 import (
    BlockEnd, BlockStart, Counter, DistantSignal, Element, MQTTDispatcher, OuterButton, Route, Signal, Tower,
    Track, Turnout)


def get_async_mock(return_value):
    """Returns a mock object that wraps an async method."""
    async def async_mock(*args, **kwargs):
        return return_value

    return Mock(wraps=async_mock)


def get_tower_mock():
    tower = MagicMock()
    tower.elements = {}
    tower.publish = MagicMock()
    tower.panel_topic = lambda k, v: f'panel/{k}/{v}'
    tower.trackside_topic = lambda k, v: f'trackside/{k}/{v}'
    tower.dispatcher = MQTTDispatcher(tower)
    tower.is_outer_button = MagicMock(return_value=False)
    return tower


class ElementTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.uat = Element(self.tower, 'uat')
        self.uat.reset()
        self.tower.publish.reset_mock()

    def test_manager(self):
        self.assertIn(self.uat, Element.objects.all())
        self.assertEqual(Element.objects.get('uat'), self.uat)
        self.assertIsNone(Element.objects.get('other'))

    def test_init(self):
        Element.objects.reset_all()
        self.assertEqual(self.uat.value, '0', 'correctly initialized')
        self.tower.publish.assert_called_once_with('panel/element/uat', b'0')

    def test_update(self):
        self.uat.update(occupied=1)
        self.assertEqual(self.uat.value, '1', 'changed after set()')
        self.tower.publish.assert_called_once_with('panel/element/uat', b'1')
        self.uat.occupied = 0
        self.assertEqual(self.uat.value, '0', 'changed after property=0')

    def test_invalid_property(self):
        with self.assertRaises(KeyError) as c:
            self.uat.update(invalid='foo')


class BlockEndTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.block_start_topic = 'blockstart'
        self.clearance_lock_release_topic = 'a_track_occupied'
        self.uat = BlockEnd(self.tower, 'uat', blockstart_topic=self.block_start_topic,
                            clearance_lock_release_topic=self.clearance_lock_release_topic)
        self.uat.reset()
        self.tower.publish.reset_mock()

    def test_init(self):
        self.assertNotEqual(Element.objects, BlockEnd.objects)
        self.assertIn(self.uat, BlockEnd.objects.all())
        self.uat.reset()
        self.tower.publish.assert_called_once_with('panel/blockend/uat', b'0,0,1')

        self.tower.publish.reset_mock()
        self.uat.update(occupied=True)
        self.tower.publish.assert_called_once_with('panel/blockend/uat', b'1,0,1')

        self.tower.publish.reset_mock()
        self.uat.update(blocked=True)
        self.tower.publish.assert_called_once_with('panel/blockend/uat', b'1,1,1')

        self.tower.publish.reset_mock()
        self.uat.update(clearance_lock=False)
        self.tower.publish.assert_called_once_with('panel/blockend/uat', b'1,1,0')

    def test_on_button_alone(self):
        self.tower.dispatcher.dispatch_one(self.tower.trackside_topic('block', self.block_start_topic), '1')
        self.tower.dispatcher.dispatch_one(self.tower.trackside_topic('track', self.clearance_lock_release_topic), '0')

        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.assertEqual(self.uat.blocked, True, 'is still blocked')
        self.assertEqual(self.uat.clearance_lock, False, 'clearance is still unlocked')

    def test_on_button_with_blockgroupbutton_clearance_lock(self):
        self.tower.dispatcher.dispatch_one(self.tower.trackside_topic('block', self.block_start_topic), '1')
        self.tower.dispatcher.dispatch_one(self.tower.trackside_topic('track', self.clearance_lock_release_topic), '1')
        self.tower.is_outer_button = MagicMock(return_value=True)

        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.assertEqual(self.uat.blocked, True, 'is still blocked')
        self.assertEqual(self.uat.clearance_lock, True, 'clearance is still locked')

    def test_on_button_with_blockgroupbutton(self):
        self.tower.dispatcher.dispatch_one(self.block_start_topic, '1')
        self.tower.dispatcher.dispatch_one(self.clearance_lock_release_topic, '0')
        self.tower.is_outer_button = MagicMock(return_value=True)

        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.assertEqual(self.uat.blocked, False, 'is unblocked')
        self.assertEqual(self.uat.clearance_lock, True, 'clearance is locked again')


class BlockStartTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.blockend_topic = 'blockend'
        self.blocking_track_topic = 'a_track_occupied'
        self.uat = BlockStart(self.tower, 'uat', blockend_topic=self.blockend_topic,
                              blocking_track_topic=self.blocking_track_topic)
        self.uat.reset()
        self.tower.publish.reset_mock()

    def test_init(self):
        self.assertIn(self.uat, BlockStart.objects.all())
        self.uat.reset()
        self.tower.publish.assert_called_once_with('panel/blockstart/uat', b'0,0')

        self.tower.publish.reset_mock()
        self.uat.update(occupied=True)
        self.tower.publish.assert_called_once_with('panel/blockstart/uat', b'1,0')

        self.tower.publish.reset_mock()
        self.uat.update(blocked=True)
        self.tower.publish.assert_called_once_with('panel/blockstart/uat', b'1,1')

    def test_blocking(self):
        self.assertEqual(self.uat.blocked, False)
        self.tower.dispatcher.dispatch_one(self.tower.trackside_topic('track', self.blocking_track_topic), '1')
        self.assertEqual(self.uat.blocked, False)
        self.tower.dispatcher.dispatch_one(self.tower.trackside_topic('track', self.blocking_track_topic), '0')
        calls = [call('panel/blockstart/uat', b'0,1')]
        self.tower.publish.assert_has_calls(calls)

    def test_unblocking(self):
        self.uat.blocked = True
        self.tower.dispatcher.dispatch_one(self.tower.trackside_topic('block', self.blockend_topic), '0')
        self.tower.publish.assert_called_once_with('panel/blockstart/uat', b'0,0')


class CounterTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.button = OuterButton(self.tower, 'uat').add_counter()
        self.uat = self.button.counter
        self.uat.reset()
        self.tower.publish.reset_mock()

    def test_init(self):
        self.assertIn(self.uat, Counter.objects.all())
        self.uat.reset()
        self.tower.publish.assert_called_once_with('panel/counter/uat', b'0')

    def test_increment(self):
        self.uat.increment()
        self.tower.publish.assert_called_once_with('panel/counter/uat', b'1')


class DistantSignalTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.home = Signal(self.tower, 'H').add_home()
        self.uat = DistantSignal(self.tower, 'uat', 'H')
        self.uat.reset()
        self.tower.publish.reset_mock()

    def test_init(self):
        self.assertIn(self.uat, DistantSignal.objects.all())
        self.assertIn(f'{self.uat}', [name for (name, _) in self.home.on_update.subscribers])
        self.uat.reset()
        self.tower.publish.assert_called_once_with('panel/signal/uat', b'Vr0')

    def test_proceed(self):
        self.home.start_home('Hp1')
        calls = [call('panel/signal/H', b'Hp1'), call('panel/signal/uat', b'Vr1')]
        self.tower.publish.assert_has_calls(calls)

        self.uat.reset()
        self.home.start_halt()
        calls = [call('panel/signal/H', b'Hp0'), call('panel/signal/uat', b'Vr0')]
        self.tower.publish.assert_has_calls(calls)


class DistantSignalMountedAtTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.mounted_at = Signal(self.tower, 'G').add_home()
        self.home = Signal(self.tower, 'H').add_home()
        self.uat = DistantSignal(self.tower, 'uat', 'H', 'G')
        self.uat.reset()
        self.home.reset()
        self.mounted_at.reset()
        self.tower.publish.reset_mock()

    def test_init(self):
        self.assertIn(self.uat, DistantSignal.objects.all())
        self.assertIn(f'{self.uat}', [name for (name, _) in self.home.on_update.subscribers])
        self.uat.reset()
        self.tower.publish.assert_called_once_with('panel/signal/uat', b'-')

    def test_proceed(self):
        self.home.start_home('Hp1')
        calls = [call('panel/signal/H', b'Hp1'), call('panel/signal/uat', b'-')]
        self.tower.publish.assert_has_calls(calls)

        self.uat.reset()
        self.home.start_halt()
        calls = [call('panel/signal/H', b'Hp0'), call('panel/signal/uat', b'-')]
        self.tower.publish.assert_has_calls(calls)

    def test_proceed_with_mounted_at_hp1(self):
        self.mounted_at.aspect = 'Hp1'
        self.home.start_home('Hp1')
        calls = [call('panel/signal/H', b'Hp1'), call('panel/signal/uat', b'Vr1')]
        self.tower.publish.assert_has_calls(calls)

        self.uat.reset()
        self.home.start_halt()
        calls = [call('panel/signal/H', b'Hp0'), call('panel/signal/uat', b'Vr0')]
        self.tower.publish.assert_has_calls(calls)


class DistantSignalWithDivergingRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.turnout = Turnout(self.tower, 'W1')
        self.home1 = Signal(self.tower, 'H1').add_home()
        self.home2 = Signal(self.tower, 'H2').add_home()
        self.uat = DistantSignal(self.tower, 'uat', {'W1': ['H1', 'H2']})
        self.uat.reset()
        self.tower.publish.reset_mock()

    def test_init(self):
        self.assertIn(self.uat, DistantSignal.objects.all())
        self.assertIn(f'{self.uat}', [name for (name, _) in self.home1.on_update.subscribers])
        self.assertIn(f'{self.uat}', [name for (name, _) in self.home2.on_update.subscribers])
        self.uat.reset()
        self.tower.publish.assert_called_once_with('panel/signal/uat', b'Vr0')

    def test_proceed_straight(self):
        self.turnout.position = False
        self.home1.start_home('Hp1')
        calls = [call('panel/signal/H1', b'Hp1'), call('panel/signal/uat', b'Vr1')]
        self.tower.publish.assert_has_calls(calls)

    def test_stop_straight(self):
        self.turnout.position = False
        self.home1.aspect = 'Hp1'
        self.home1.start_halt()
        calls = [call('panel/signal/H1', b'Hp0'), call('panel/signal/uat', b'Vr0')]
        self.tower.publish.assert_has_calls(calls)

    def test_proceed_diverging_other_signal(self):
        self.turnout.position = True
        self.home1.start_home('Hp1')
        calls = [call('panel/signal/H1', b'Hp1')]
        self.tower.publish.assert_has_calls(calls)

    def test_proceed_diverging(self):
        self.turnout.position = True
        self.home2.start_home('Hp1')
        calls = [call('panel/signal/H2', b'Hp1'), call('panel/signal/uat', b'Vr1')]
        self.tower.publish.assert_has_calls(calls)

    def test_stop_diverging(self):
        self.turnout.position = True
        self.home2.aspect = 'Hp1'
        self.home2.start_halt()
        calls = [call('panel/signal/H2', b'Hp0'), call('panel/signal/uat', b'Vr0')]
        self.tower.publish.assert_has_calls(calls)


class OuterButtonTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.uat = OuterButton(self.tower, 'uat')
        self.uat.reset()
        self.tower.publish.reset_mock()

    def test_manager(self):
        self.assertIn(self.uat, OuterButton.objects.all())
        self.assertEqual(OuterButton.objects.get('uat'), self.uat)
        self.assertIsNone(OuterButton.objects.get('other'))

    def test_init(self):
        OuterButton.objects.reset_all()
        self.assertEqual(self.uat.value, '', 'correctly initialized')
        self.assertFalse(self.tower.publish.called, 'has no publishable properties')

    def test_update(self):
        with self.assertRaises(KeyError) as c:
            self.uat.update(occupied=1)

    def test_invalid_property(self):
        with self.assertRaises(KeyError) as c:
            self.uat.update(invalid='foo')


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.s1 = Signal(self.tower, 's1')
        self.s2 = Signal(self.tower, 's2')
        self.uat = Route(self.tower, self.s1, self.s2, 'release_topic')

    def test_init(self):
        self.assertIn(self.uat, Route.objects.all())


class SignalTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.uat = Signal(self.tower, 'uat')
        self.s2 = Signal(self.tower, 's2')
        self.route = Route(self.tower, self.uat, self.s2, 'track-1')
        self.ersgt = OuterButton(self.tower, 'ErsGT').add_counter()
        self.fht = OuterButton(self.tower, 'FHT').add_counter()
        # self.route.start = MagicMock()
        # self.route.unlock = MagicMock()
        self.uat.reset()
        self.tower.publish.reset_mock()

    def test_init(self):
        self.assertIn(self.uat, Signal.objects.all())
        self.uat.reset()
        self.tower.publish.assert_called_once_with('panel/signal/uat', b'Hp0')

    def test_shunting_no_shunting_aspect(self):
        self.tower.is_outer_button = lambda b: b=='SGT'
        self.tower.publish.reset_mock()
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.assertFalse(self.tower.publish.called)

    def test_shunting_no_outer_button(self):
        self.uat.add_shunting()
        self.tower.is_outer_button = lambda b: False
        self.tower.publish.reset_mock()
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.assertFalse(self.tower.publish.called)

    def test_shunting_shunting_aspect(self):
        self.uat.add_shunting()
        self.tower.is_outer_button = lambda b: b=='SGT'
        self.tower.publish.reset_mock()
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.tower.publish.assert_called_once_with('panel/signal/uat', b'Sh1')

    def test_set_to_stop_from_sh1(self):
        self.uat.aspect = 'Sh1'
        self.tower.is_outer_button = lambda b: b=='HaGT'
        self.tower.publish.reset_mock()
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.tower.publish.assert_called_once_with('panel/signal/uat', b'Hp0')

    def test_set_to_stop_from_hp1(self):
        self.uat.aspect = 'Hp1'
        self.tower.is_outer_button = lambda b: b=='HaGT'
        self.tower.publish.reset_mock()
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.tower.publish.assert_called_once_with('panel/signal/uat', b'Hp0')

    def test_alt_no_alt_aspect(self):
        self.tower.is_outer_button = lambda b: b=='ErsGT'
        self.tower.publish.reset_mock()
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.assertFalse(self.tower.publish.called)

    def test_alt_no_outer_button(self):
        self.uat.add_alt()
        self.tower.is_outer_button = lambda b: False
        self.tower.publish.reset_mock()
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.assertFalse(self.tower.publish.called)

    async def async_alt_alt_aspect(self):
        self.uat.add_alt()
        self.uat.alt_timeout = 0.001
        self.tower.is_outer_button = lambda b: b=='ErsGT'
        self.tower.publish.reset_mock()
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.assertIsNotNone(self.uat.task, 'alt aspect is started')
        await self.uat.task
        calls = [call('panel/signal/uat', b'Zs1'), call('panel/signal/uat', b'Hp0')]
        self.tower.publish.assert_has_calls(calls)

    def test_alt_alt_aspect(self):
        asyncio.get_event_loop().run_until_complete(self.async_alt_alt_aspect())

    def test_route_release(self):
        self.uat.aspect = 'Hp1'
        self.route.locked = True
        self.tower.is_outer_button = lambda b: b=='FHT'
        with patch.object(Route, 'unlock') as fn:
            self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
            fn.assert_called_once_with()

    def test_route_start(self):
        self.tower.is_outer_button = lambda b: False
        with patch.object(Route, 'start') as fn:
            self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 's2'), '1')
            self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
            fn.assert_called_once_with()


class TrackTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.uat = Track(self.tower, 'uat')
        self.uat.reset()
        self.tower.publish.reset_mock()

    def test_init(self):
        self.assertIn(self.uat, Track.objects.all())
        self.uat.reset()
        self.tower.publish.assert_called_once_with('panel/track/uat', b'0,0')

    def test_occupied(self):
        self.uat.update(occupied=1)
        self.tower.publish.assert_called_once_with('panel/track/uat', b'1,0')

    def test_locked(self):
        self.uat.update(locked=1)
        self.tower.publish.assert_called_once_with('panel/track/uat', b'0,1')


class TowerTestCase(unittest.TestCase):
    def setUp(self):
        self.client = create_autospec(MQTTClient)
        self.client.publish = get_async_mock(None)
        self.uat = Tower('uat', self.client)

    def test_init(self):
        self.assertEqual(len(self.uat.managers), 9)
        self.uat.reset_all()

    def test_is_outer_button_not_pressed(self):
        self.assertFalse(self.uat.is_outer_button('WGT'))

    def test_is_outer_button_wgt_pushed(self):
        b = OuterButton.objects.get('WGT')
        self.assertIsNotNone(b)
        b.pushed = True
        self.assertTrue(self.uat.is_outer_button('WGT'))

    def test_is_outer_button_multiple_pushed(self):
        b = OuterButton.objects.get('WGT')
        self.assertIsNotNone(b)
        b.pushed = True
        b = OuterButton.objects.get('ErsGT')
        self.assertIsNotNone(b)
        b.pushed = True
        self.assertFalse(self.uat.is_outer_button('WGT'))

    async def async_publish(self):
        self.uat.connected = True
        await self.uat.publish('topic', b'value')
        self.client.publish.assert_called_once_with('topic', b'value')

    def test_publish(self):
        asyncio.get_event_loop().run_until_complete(self.async_publish())


class TurnoutTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.uat = Turnout(self.tower, 'uat')
        self.uat.reset()
        self.tower.publish.reset_mock()

    def test_init(self):
        self.assertIn(self.uat, Turnout.objects.all())
        self.uat.reset()
        self.tower.publish.assert_called_once_with('panel/turnout/uat', b'0,0,0,0,0')

    def test_change_button_alone(self):
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')

    async def async_change_with_outer_button(self):
        self.uat.moving_timeout = 0.001
        self.tower.is_outer_button = lambda b: b=='WGT'
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        self.assertIsNotNone(self.uat.task, 'change task is running')
        await self.uat.task
        calls = [call('panel/turnout/uat', b'0,1,1,0,0'), call('panel/turnout/uat', b'0,1,0,0,0')]
        self.tower.publish.assert_has_calls(calls)

    def test_change_with_outer_button(self):
        asyncio.get_event_loop().run_until_complete(self.async_change_with_outer_button())

    def test_change_locked(self):
        self.tower.is_outer_button = lambda b: b=='WGT'
        self.uat.locked = True
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        with patch.object(Turnout, 'start_change') as fn:
            self.assertFalse(fn.called, 'no change if locked')

    def test_change_occupied(self):
        self.tower.is_outer_button = lambda b: b=='WGT'
        self.uat.occupied = True
        self.tower.dispatcher.dispatch_one(self.tower.panel_topic('button', 'uat'), '1')
        with patch.object(Turnout, 'start_change') as fn:
            self.assertFalse(fn.called, 'no change if locked')