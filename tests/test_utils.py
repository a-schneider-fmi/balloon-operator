#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for utils module.

Copyright (C) 2021 Andreas Schneider <andreas.schneider@fmi.fi>

This file is part of Balloon Operator.

Balloon Operator is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.

Balloon Operator is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
Balloon Operator. If not, see <https://www.gnu.org/licenses/>.
"""

from balloon_operator import utils
import numpy as np
import datetime

def test_alt2press(verbose=False):
    """
    Unit test for alt2press and press2alt.
    """
    p0 = np.random.normal(101325., 2000.) # random sea-level pressure
    if verbose: print(p0)
    assert(utils.alt2press(0., p0=p0) == p0)
    altitudes = np.random.rand(30)*10000.
    pressures = utils.alt2press(altitudes, p0=p0)
    eps = (utils.press2alt(pressures, p0=p0) - altitudes) / altitudes
    if verbose: print(eps)
    assert (eps < 1e-10).all()

def test_roundSeconds(verbose=False):
    """
    Unit test for roundSeconds
    """
    dt = datetime.datetime(2021, 1, 1, 0, 0, 5, np.random.randint(1000000))
    dt_rounded = utils.roundSeconds(dt) # round
    if verbose: print('{} -> {}, {}'.format(dt, dt_rounded, dt-dt_rounded))
    if dt_rounded > dt:
        assert(dt_rounded - dt <= datetime.timedelta(milliseconds=500))
    else:
        assert(dt - dt_rounded < datetime.timedelta(milliseconds=500))
    assert(dt_rounded.microsecond == 0)

    dt_rounded = utils.roundSeconds(dt, 1000000) # round down
    if verbose: print('{} -> {}, {}'.format(dt, dt_rounded, dt-dt_rounded))
    assert(dt_rounded <= dt and dt - dt_rounded < datetime.timedelta(seconds=1))
    assert(dt_rounded.microsecond == 0)


def test_roundHours(verbose=False):
    """
    Unit test for roundHours
    """
    dt = datetime.datetime.utcnow()
    dt_rounded = utils.roundHours(dt)
    if verbose: print('{} -> {}, {}'.format(dt, dt_rounded, dt-dt_rounded))
    if dt_rounded > dt:
        assert(dt_rounded - dt <= datetime.timedelta(minutes=30))
    else:
        assert(dt - dt_rounded < datetime.timedelta(minutes=30))
    assert(dt_rounded.minute == 0 and dt_rounded.second == 0)

    dt_rounded = utils.roundHours(dt, 1) # round up
    if verbose: print('{} -> {}, {}'.format(dt, dt_rounded, dt_rounded - dt))
    assert(dt_rounded >= dt and dt_rounded - dt < datetime.timedelta(minutes=59))
    assert(dt_rounded.minute == 0 and dt_rounded.second == 0)


if __name__ == "__main__":
    test_alt2press(verbose=True)
    test_roundSeconds(verbose=True)
    test_roundHours(verbose=True)
