#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from unittest.mock import MagicMock

from frischen.spdrl20 import BlockEnd, Tower, Element, Signal, Turnout


class ElementTestCase(unittest.TestCase):
    def setUp(self):
        self.tower = MagicMock()
        self.tower.elements = {}
        self.tower.publish = MagicMock()
        self.tower.topic = lambda k, v: f'{k}/{v}'

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

# class BlockEndTestCase(unittest.TestCase):
#     def setUp(self):
#         self.tower = MagicMock()
#         self.tower.elements = {}
#         self.tower.publish = MagicMock()
#         self.tower.topic = lambda k, v: f'{k}/{v}'
# 
# 
#     def test_init(self):
#         e = BlockEnd(self.tower, 'uat')
#         self.assertIn(e.kind, self.tower.elements)
#         elements = self.tower.elements[e.kind]
#         self.assertIn(e.name, elements)
#         BlockEnd.initialize_all(self.tower)
#         self.tower.publish.assert_called_with('blockend/uat', b'0')
# 
#     def test_on_released_alone(self):
#         e = BlockEnd(self.tower, 'uat')
#         self.tower.is_outer_button = MagicMock(return_value=False)
#         e.on_button(self.tower, 1)
#         self.assertEqual(e.value, 0)
# 
#     def test_on_released_with_blockgroupbutton(self):
#         e = BlockEnd(self.tower, 'uat')
#         self.tower.is_outer_button = MagicMock(return_value=True)
#         e.on_button(self.tower, 1)
#         self.assertEqual(e.value, 1)
