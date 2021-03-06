#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility functions.

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

from balloon_operator import constants
import datetime


def alt2press(h, p0=101325., T0=288.15, L=0.0065):
    """
    Computes pressure from altitude according to the international height formula.

    @param h altitude (in metres)
    @param p0 surface pressure (default: 101325 Pa = 1013.24 hPa)
    @param T0 surface temperature (default: 288.15 K = 15°C)
    @param L lapse rate (default: 0.0065 K/m = 6.5K/km)

    @return p pressure (in Pa)
        
    The formula is
     p = p0 (1 − h L/T0)^(g M/(R0 L))
    where
     p: pressure
     h: altitude
     p0: sea level standard atmospheric pressure (101325 Pa)
     L: temperature lapse rate, for dry air L = g/cp = 0.0065 K/m
     cp: specific heat at constant pressure (ca. 1007 J/(kg K))
     T0: sea level standard temperature 288.15 K
     g: Earth-surface gravitational acceleration (9.80665 m/s^2)
     M: molar mass of dry air (0.0289644 kg/mol)
     R0: universal gas constant (8.31447 J/(mol K))
    All constants are taken from the constants module.
    
    References:
    https://en.wikipedia.org/wiki/Atmospheric_pressure
    https://de.wikipedia.org/wiki/Barometrische_H%C3%B6henformel#Internationale_H%C3%B6henformel
    """
    p = p0 * (1. - L*h/T0)**(constants.gravity*constants.mass["dry_air"]/(constants.gas_constant*L))
    return p


def press2alt(p, p0=101325., T0=288.15, L=0.0065):
    """
    Computes altitude from pressure according to the international height formula.

    @param p pressure (in Pa)
    @param p0 surface pressure (default: 101325 Pa = 1013.24 hPa)
    @param T0 surface temperature (default: 288.15 K = 15°C)
    @param L lapse rate (default: 0.0065 K/m = 6.5K/km)

    @return h altitude (in m)

    Uses an inversion of the pressure formula in alt2press(), which is
     h = T0/L ( 1 - (p/p0)^(R0 L/(g M)) )
    where
     p: pressure
     h: altitude
     p0: sea level standard atmospheric pressure (101325 Pa)
     L: temperature lapse rate, for dry air L = g/cp = 0.0065 K/m
     cp: specific heat at constant pressure (ca. 1007 J/(kg K))
     T0: sea level standard temperature 288.15 K
     g: Earth-surface gravitational acceleration (9.80665 m/s^2)
     M: molar mass of dry air (0.0289644 kg/mol)
     R0: universal gas constant (8.31447 J/(mol K))
    All constants are taken from the constants module.

    References:
    https://en.wikipedia.org/wiki/Atmospheric_pressure
    https://de.wikipedia.org/wiki/Barometrische_H%C3%B6henformel#Internationale_H%C3%B6henformel
    """
    h = T0/L * ( 1. - (p/p0)**(L*constants.gas_constant/(constants.gravity*constants.mass["dry_air"])) )
    return h


def roundSeconds(dt: datetime.datetime, round_up_threshold=500_000) -> datetime.datetime:
    """
    Rounds a datetime object to the ext full second.

    @param dt datetime to be rounded
    @param round_up_threshold threshold in microseconds from which rounding up (default: 500_000)
        Use 1 to round up.

    @return dt rounded datetime
    """
    if dt.microsecond >= round_up_threshold:
        dt += datetime.timedelta(seconds=1)
    return dt.replace(microsecond=0)


def roundHours(dt: datetime.datetime, round_up_threshold=30) -> datetime.datetime:
    """
    Rounds a datetime object to the ext full hour.

    @param dt datetime to be rounded
    @param round_up_threshold threshold in minutes from which to round up (default: 30)

    @return dt rounded datetime
    """
    new_hour = dt.hour + (1 if dt.minute >= round_up_threshold else 0)
    dt_rounded = datetime.datetime.combine(dt.date(), datetime.time(new_hour))

    return dt_rounded
