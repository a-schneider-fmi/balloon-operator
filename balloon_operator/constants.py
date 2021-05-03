#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Physical constants

Created on Sat Apr 24 19:30:45 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
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
