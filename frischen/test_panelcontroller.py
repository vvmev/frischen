#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from unittest.mock import MagicMock

from frischen.panelcontroller import BlockEnd, Controller, Element, Signal, Switch


class ElementTestCase(unittest.TestCase):
    def setUp(self):
        self.controller = MagicMock()
        self.controller.elements = {}

    def test_init(self):
        e = Element(self.controller, 'uat')
        self.assertIn(e.kind, self.controller.elements)
        elements = self.controller.elements[e.kind]
        self.assertIn(e.name, elements)
