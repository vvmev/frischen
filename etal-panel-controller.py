#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio

from frischen.panelcontroller import BlockEnd, Controller, Signal, Switch

logger = logging.getLogger(__name__)


async def main():
    controller = Controller('frischen/etal/panel')
    BlockEnd(controller, 'blockend-d')
    BlockEnd(controller, 'blockend-m')
    Signal(controller, 'p1p3').distant()
    Signal(controller, 'A').home().alt()
    Signal(controller, 'a').distant()
    Signal(controller, 'P1').home().shunting().alt()
    Signal(controller, 'P3').home().shunting().alt()
    Signal(controller, 'N2').home().shunting().alt()
    Signal(controller, 'N3').home().shunting().alt()
    Signal(controller, 'F').home().alt().distant()
    Signal(controller, 'f').distant()
    Signal(controller, 'n2n3').distant()
    for n in ['W1', 'W2', 'W3', 'W4', 'W10', 'W11', 'W12', 'W13']:
        Switch(controller, n)
    await controller.connect()
    await controller.handle()

if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
