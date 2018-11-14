#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio

from frischen.spdrl20 import (
    BlockEnd, BlockStart, Tower, DistantSignal, Route, Signal, Turnout, Track)

logger = logging.getLogger(__name__)


async def main():
    tower = Tower('frischen/etal/panel')
    BlockEnd(tower, 'blockend-d')
    BlockEnd(tower, 'blockend-m')
    BlockStart(tower, 'blockstart-d')
    BlockStart(tower, 'blockstart-m')

    for n in ['W1', 'W2', 'W3', 'W4', 'W10', 'W11', 'W12', 'W13']:
        Turnout(tower, n)

    Signal(tower, 'p1p3')
    Signal(tower, 'P1').home().shunting().alt()
    Signal(tower, 'P3').home().shunting().alt()
    Signal(tower, 'N2').home().shunting().alt()
    Signal(tower, 'N3').home().shunting().alt()
    Signal(tower, 'A').home().alt()
    Signal(tower, 'F').home().alt()
    Signal(tower, 'n2n3')
    DistantSignal(tower, 'a', 'A')
    DistantSignal(tower, 'n2n3', {'W3': ['N2', 'N3']}, 'A')
    DistantSignal(tower, 'p1p3', {'W13': ['P1', 'P3']}, 'F')
    DistantSignal(tower, 'f', 'F')

    Track(tower, '1-1')
    Track(tower, '1-4')
    Track(tower, '1-6')
    Track(tower, '2-1')
    Track(tower, '2-2')
    Track(tower, '2-3')
    Track(tower, '2-4')
    Track(tower, '2-5')
    Track(tower, '2-6')
    Track(tower, '3-4')

    Route(tower, 'P1', 'p1p3') \
        .turnout('W1', 0) \
        .track('1-1') \
        .flankProtection('W2', 0)

    Route(tower, 'F', 'P1') \
        .turnout('W13', 0) \
        .track('1-4') \
        .flankProtection('W12', 0)

    Route(tower, 'P3', 'p1p3') \
        .turnout('W4', 1) \
        .turnout('W3', 1) \
        .track('2-3') \
        .turnout('W2', 1) \
        .turnout('W1', 1) \
        .track('1-1') \

    Route(tower, 'F', 'P3') \
        .turnout('W13', 1) \
        .turnout('W12', 1) \
        .track('2-5') \
        .turnout('W11', 1) \
        .turnout('W10', 1) \
        .track('3-4') \
        .flankProtection('W3', 1) \
        .flankProtection('W4', 1)

    Route(tower, 'A', 'N2') \
        .track('2-2') \
        .turnout('W2', 0) \
        .track('2-3') \
        .turnout('W3', 0) \
        .track('2-4') \
        .flankProtection('W1', 0) \
        .flankProtection('W4', 0)

    Route(tower, 'A', 'N3') \
        .track('2-2') \
        .turnout('W2', 0) \
        .track('2-3') \
        .turnout('W3', 1) \
        .turnout('W4', 1) \
        .track('3-4') \
        .flankProtection('W1', 0)

    Route(tower, 'N2', 'n2n3') \
        .turnout('W11', 0) \
        .track('2-5') \
        .turnout('W12', 0) \
        .track('2-6') \
        .flankProtection('W10', 0) \
        .flankProtection('W13', 0)

    Route(tower, 'N3', 'n2n3') \
        .turnout('W10', 1) \
        .turnout('W11', 1) \
        .track('2-5') \
        .turnout('W12', 0) \
        .track('2-6') \
        .flankProtection('W13', 0)

    await tower.connect()
    await tower.handle()

if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
