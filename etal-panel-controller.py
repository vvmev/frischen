#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio

from frischen.spdrl20 import (
    BlockEnd, BlockStart, Tower, DistantSignal, Route, Signal, Turnout, Track)

logger = logging.getLogger(__name__)


async def main():
    tower = Tower('etal')
    BlockEnd(tower, 'blockend-d', 'd-e', 'W13')
    BlockEnd(tower, 'blockend-m', 'm-e', 'W2')
    BlockStart(tower, 'blockstart-d', 'e-b', '2-6')
    BlockStart(tower, 'blockstart-m', 'e-m', '1-1')

    for n in ['W1', 'W2', 'W3', 'W4', 'W10', 'W11', 'W12', 'W13']:
        Turnout(tower, n)

    Signal(tower, 'p1p3')
    Signal(tower, 'P1').add_home().add_shunting().add_alt()
    Signal(tower, 'P3').add_home().add_shunting().add_alt()
    Signal(tower, 'N2').add_home().add_shunting().add_alt()
    Signal(tower, 'N3').add_home().add_shunting().add_alt()
    Signal(tower, 'A').add_home().add_alt()
    Signal(tower, 'F').add_home().add_alt()
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

    Route(tower, 'P1', 'p1p3', 'W1') \
        .add_turnout('W1', 0) \
        .add_track('1-1') \
        .add_flank_protection('W2', 0)

    Route(tower, 'F', 'P1', 'W13') \
        .add_turnout('W13', 0) \
        .add_track('1-4') \
        .add_flank_protection('W12', 0)

    Route(tower, 'P3', 'p1p3', 'W1') \
        .add_turnout('W4', 1) \
        .add_turnout('W3', 1) \
        .add_track('2-3') \
        .add_turnout('W2', 1) \
        .add_turnout('W1', 1) \
        .add_track('1-1') \

    Route(tower, 'F', 'P3', 'W13') \
        .add_turnout('W13', 1) \
        .add_turnout('W12', 1) \
        .add_track('2-5') \
        .add_turnout('W11', 1) \
        .add_turnout('W10', 1) \
        .add_track('3-4') \
        .add_flank_protection('W3', 1) \
        .add_flank_protection('W4', 1)

    Route(tower, 'A', 'N2', 'W2') \
        .add_track('2-2') \
        .add_turnout('W2', 0) \
        .add_track('2-3') \
        .add_turnout('W3', 0) \
        .add_track('2-4') \
        .add_flank_protection('W1', 0) \
        .add_flank_protection('W4', 0)

    Route(tower, 'A', 'N3', 'W2') \
        .add_track('2-2') \
        .add_turnout('W2', 0) \
        .add_track('2-3') \
        .add_turnout('W3', 1) \
        .add_turnout('W4', 1) \
        .add_track('3-4') \
        .add_flank_protection('W1', 0)

    Route(tower, 'N2', 'n2n3', 'W12') \
        .add_turnout('W11', 0) \
        .add_track('2-5') \
        .add_turnout('W12', 0) \
        .add_track('2-6') \
        .add_flank_protection('W10', 0) \
        .add_flank_protection('W13', 0)

    Route(tower, 'N3', 'n2n3', 'W12') \
        .add_turnout('W10', 1) \
        .add_turnout('W11', 1) \
        .add_track('2-5') \
        .add_turnout('W12', 0) \
        .add_track('2-6') \
        .add_flank_protection('W13', 0)

    await tower.run()

if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
