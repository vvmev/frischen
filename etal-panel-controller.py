#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio

from frischen.panelcontroller import Switch, SwitchController

logger = logging.getLogger(__name__)


async def main():
    controller = SwitchController('frischen/etal/panel')
    switches = {k: Switch(controller, k)
                for k in ['W1', 'W2', 'W3', 'W4', 'W10', 'W11', 'W12', 'W13']}
    controller.switches = switches
    await controller.connect()
    await controller.handle()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
