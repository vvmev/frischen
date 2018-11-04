#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio

from frischen.panelcontroller import Signal, Switch, SwitchController

logger = logging.getLogger(__name__)


async def main():
    controller = SwitchController('frischen/etal/panel')
    signals = {}
    signals['p1p3'] = Signal(controller, 'p1p3').distant()
    signals['A'] = Signal(controller, 'A').home().alt()
    signals['a'] = Signal(controller, 'a').distant()
    signals['P1'] = Signal(controller, 'P1').home().shunting().alt()
    signals['P3'] = Signal(controller, 'P3').home().shunting().alt()
    signals['N2'] = Signal(controller, 'N2').home().shunting().alt()
    signals['N3'] = Signal(controller, 'N3').home().shunting().alt()
    signals['F'] = Signal(controller, 'F').home().alt().distant()
    signals['f'] = Signal(controller, 'f').distant()
    signals['n2n3'] = Signal(controller, 'n2n3').distant()
    controller.signals = signals
    switches = {k: Switch(controller, k)
                for k in ['W1', 'W2', 'W3', 'W4', 'W10', 'W11', 'W12', 'W13']}
    controller.switches = switches
    await controller.connect()
    await controller.handle()

if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
