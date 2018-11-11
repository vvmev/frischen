#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from unittest.mock import MagicMock

from frischen.panelcontroller import BlockEnd, Controller, Element, Signal, Turnout


class ElementTestCase(unittest.TestCase):
    def setUp(self):
        self.controller = MagicMock()
        self.controller.elements = {}
        self.controller.publish = MagicMock()
        self.controller.topic = lambda k, v: f'{k}/{v}'

    def test_init(self):
        e = Element(self.controller, 'uat')
        self.assertIn(e.kind, self.controller.elements)
        elements = self.controller.elements[e.kind]
        self.assertIn(e.name, elements)
        Element.initialize_all(self.controller)
        self.controller.publish.assert_called_with('element/uat', b'0')


class BlockEndTestCase(unittest.TestCase):
    def setUp(self):
        self.controller = MagicMock()
        self.controller.elements = {}
        self.controller.publish = MagicMock()
        self.controller.topic = lambda k, v: f'{k}/{v}'


    def test_init(self):
        e = BlockEnd(self.controller, 'uat')
        self.assertIn(e.kind, self.controller.elements)
        elements = self.controller.elements[e.kind]
        self.assertIn(e.name, elements)
        BlockEnd.initialize_all(self.controller)
        self.controller.publish.assert_called_with('blockend/uat', b'0')

    def test_on_released_alone(self):
        e = BlockEnd(self.controller, 'uat')
        self.controller.is_outer_button = MagicMock(return_value=False)
        e.on_button(self.controller, 1)
        self.assertEqual(e.value, 0)

    def test_on_released_with_blockgroupbutton(self):
        e = BlockEnd(self.controller, 'uat')
        self.controller.is_outer_button = MagicMock(return_value=True)
        e.on_button(self.controller, 1)
        self.assertEqual(e.value, 1)
