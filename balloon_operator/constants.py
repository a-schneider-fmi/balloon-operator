#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module for physical constants

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

gravity = 9.80665 # gravitational acceleration in m/s^2
gas_constant = 8.3144598 # universal gas constant in J/mol/K
specific_gas_constant = { # specific gas constant
    'dry_air': 287.04 # J/(kg K)
}
avogadro = 6.02214076e23 # Avogadro's constant in molecules per mol
mass = {
    'dry_air': 0.028964, # molar mass of dry air in kg/mol (source: https://en.wikipedia.org/wiki/Density_of_air#Humidity_.28water_vapor.29)
    'water': 0.018016, # molar mass of water vapor in kg/mol
}
density = {
    'air': 1.205, # air density in kg/m^2 at 0°C and 101kPa
    'liquid_water': 1000.0 # density of liquid fresh water at 4 degress Celsius
}
specific_heat_constant_pressure = 1007 # specific heat of air at constant pressure in J/(kg K)
sea_level_standard_pressure = 101325 # Pa
planck = 6.62607015e-34 # Planck's constant in J s
boltzmann = 1.380649e-23 # Blotzmann's constant in J/K
r_earth = 6371000. # Earth radius in m
temperature_lapse_rate = gravity/specific_heat_constant_pressure
pressure_scale_height = 250.0*gas_constant/(0.029*gravity) # pressure scale height at 250K (mean atmospheric temperature on Earth)
