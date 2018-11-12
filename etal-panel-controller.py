#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio

from frischen.panelcontroller import (
    BlockEnd, BlockStart, Controller, DistantSignal, Route, Signal, Turnout, Track)

logger = logging.getLogger(__name__)


async def main():
    controller = Controller('frischen/etal/panel')
    BlockEnd(controller, 'blockend-d')
    BlockEnd(controller, 'blockend-m')
    BlockStart(controller, 'blockstart-d')
    BlockStart(controller, 'blockstart-m')

    for n in ['W1', 'W2', 'W3', 'W4', 'W10', 'W11', 'W12', 'W13']:
        Turnout(controller, n)

    Signal(controller, 'p1p3')
    Signal(controller, 'P1').home().shunting().alt()
    Signal(controller, 'P3').home().shunting().alt()
    Signal(controller, 'N2').home().shunting().alt()
    Signal(controller, 'N3').home().shunting().alt()
    Signal(controller, 'A').home().alt()
    Signal(controller, 'F').home().alt()
    Signal(controller, 'n2n3')
    DistantSignal(controller, 'a', 'A')
    DistantSignal(controller, 'n2n3', {'W3': ['N2', 'N3']}, 'A')
    DistantSignal(controller, 'p1p3', {'W13': ['P1', 'P3']}, 'F')
    DistantSignal(controller, 'f', 'F')

    Track(controller, '1-1')
    Track(controller, '1-4')
    Track(controller, '1-6')
    Track(controller, '2-1')
    Track(controller, '2-2')
    Track(controller, '2-3')
    Track(controller, '2-4')
    Track(controller, '2-5')
    Track(controller, '2-6')
    Track(controller, '3-4')

    Route(controller, 'P1', 'p1p3') \
        .turnout('W1', 0) \
        .track('1-1') \
        .flankProtection('W2', 0)

    Route(controller, 'F', 'P1') \
        .turnout('W13', 0) \
        .track('1-4') \
        .flankProtection('W12', 0)

    Route(controller, 'P3', 'p1p3') \
        .turnout('W4', 1) \
        .turnout('W3', 1) \
        .track('2-3') \
        .turnout('W2', 1) \
        .turnout('W1', 1) \
        .track('1-1') \

    Route(controller, 'F', 'P3') \
        .turnout('W13', 1) \
        .turnout('W12', 1) \
        .track('2-5') \
        .turnout('W11', 1) \
        .turnout('W10', 1) \
        .track('3-4') \
        .flankProtection('W3', 1) \
        .flankProtection('W4', 1)

    Route(controller, 'A', 'N2') \
        .track('2-2') \
        .turnout('W2', 0) \
        .track('2-3') \
        .turnout('W3', 0) \
        .track('2-4') \
        .flankProtection('W1', 0) \
        .flankProtection('W4', 0)

    Route(controller, 'A', 'N3') \
        .track('2-2') \
        .turnout('W2', 0) \
        .track('2-3') \
        .turnout('W3', 1) \
        .turnout('W4', 1) \
        .track('3-4') \
        .flankProtection('W1', 0)

    Route(controller, 'N2', 'n2n3') \
        .turnout('W11', 0) \
        .track('2-5') \
        .turnout('W12', 0) \
        .track('2-6') \
        .flankProtection('W10', 0) \
        .flankProtection('W13', 0)

    Route(controller, 'N3', 'n2n3') \
        .turnout('W10', 1) \
        .turnout('W11', 1) \
        .track('2-5') \
        .turnout('W12', 0) \
        .track('2-6') \
        .flankProtection('W13', 0)

    await controller.connect()
    await controller.handle()

if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
