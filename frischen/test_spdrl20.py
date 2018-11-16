#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from unittest.mock import MagicMock

from frischen.spdrl20 import BlockEnd, Tower, Element, Signal, Turnout


def get_tower_mock():
    tower = MagicMock()
    tower.elements = {}
    tower.publish = MagicMock()
    tower.topic = lambda k, v: f'{k}/{v}'
    return tower


class ElementTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()

    def test_init(self):
        e = Element(self.tower, 'uat')
        self.assertIn(e, Element.objects.all())
        Element.objects.initialize_all()
        self.assertEqual(e.value, '0', 'correctly initialized')
        self.tower.publish.assert_called_with('element/uat', b'0')
        e.set(occupied=1)
        self.assertEqual(e.value, '1', 'changed after set()')
        e.occupied = 0
        self.assertEqual(e.value, '0', 'changed after property=0')

class BlockEndTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = get_tower_mock()
        self.uat = BlockEnd(self.tower, 'uat')
        self.uat.initialize()

    def test_init(self):
        self.assertIn(self.uat, BlockEnd.objects.all())
        self.tower.publish.assert_called_with('blockend/uat', b'0,0')

    def test_on_released_alone(self):
        self.uat.blocked = True
        self.tower.is_outer_button = MagicMock(return_value=False)
        self.uat.on_button(True)
        self.assertEqual(self.uat.blocked, True)

    def test_on_released_with_blockgroupbutton(self):
        self.uat.blocked = True
        self.tower.is_outer_button = MagicMock(return_value=True)
        self.uat.on_button(True)
        self.assertEqual(self.uat.value, '0,1')
