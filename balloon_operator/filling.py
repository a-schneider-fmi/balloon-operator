#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute filling of the balloon.

The functionality is based on the "Totex Balloon Burst Estimator" spreadsheet
and on Jens Söder's BalloonTrajectory MATLAB program.

Created on Thu Apr  8 07:38:26 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import numpy as np
from enum import Enum

FillGas = Enum('FillGas', 'HYDROGEN HELIUM')
gas_density = {FillGas.HYDROGEN: 0.0899, FillGas.HELIUM: 0.1786} # gas density in kg/m^3 at STP (standard temperature and pressure, 0°C and 101kPa)


def readBalloonParameters(filename):
    """
    Read balloon parameter table (balloon size, burst diameter, drag coefficient)
    from CSV file.
    These data are provided by Totex in their Balloon Burst Estimator spreadsheet.

    @param filename CSV file name of the data
    @return named array with balloon parameters, names are 'weight', 'burst_diameter', 'drag_coefficient'
    """
    return np.genfromtxt(filename, delimiter='\t', skip_header=1, names=['weight', 'burst_diameter', 'drag_coefficient'])


def lookupBalloonParameters(balloon_parameter_list, balloon_weight):
    """
    Look up balloon parameters for a given balloon weight.

    @param balloon_parameters balloon parameter table as read with readBalloonParameters
    @param balloon_weight balloon weight to look up the data
    @return named array with keys 'weight', 'burst_diameter' and 'drag_coefficient', or None if the given weight is not in the list.
    """
    ind = np.where(balloon_parameter_list[:]['weight'] == balloon_weight)[0]
    if len(ind) != 1:
        return None
    else:
        return balloon_parameter_list[ind[0]]


def balloonPerformance(balloon_parameters, payload_weight, launch_volume=None, launch_radius=None, fill_gas=FillGas.HELIUM):
    """
    Compute balloon performance (ascent velocity, burst altitude) based on
    filling and payload weight.
    This is a re-implementation of the Totex Balloon Burst Estimator spreadsheet.

    @param balloon_parameters: named array or dictionary with keys 'weight', 'burst_diameter' and 'drag_coefficient'
    @param payload_weight payload weight in kg
    @param launch_volume fill volume in m^3
    @param launch_radius launch radius corresponding to balloon filling in m, alternative to launch_volume
    @param fill_gas fill gas, instance of FillGas enum
    @return free_lift, ascent_velocity, burst_height
    """
    assert(launch_volume is not None or launch_radius is not None)
    air_density = 1.205 # air density in kg/m^2 at 0°C and 101kPa
    air_density_model = 7238.3 # air density model from spread sheet
    gravity = 9.81 # gravitational acceleration in m/s^2
    if launch_radius is None: # if launch radius is not given, but launch volume
        launch_radius = (launch_volume/(4./3.*np.pi))**(1./3.)
    elif launch_volume is None: # if launch volume is not given, but launch radius
        launch_volume = 4./3.*np.pi*launch_radius**3
    burst_volume = 4./3.*np.pi*(balloon_parameters['burst_diameter']/2.)**3 # burst colume in m^3
    burst_height = -air_density_model*np.log(launch_volume/burst_volume) # burst height in m
    gross_lift = launch_volume*(air_density-gas_density[fill_gas]) # gross lift in kg
    free_lift = gross_lift - (balloon_parameters['weight']/1000. + payload_weight) # free lift in kg
    ascent_velocity = np.sign(free_lift)*np.sqrt(np.abs(free_lift)*gravity / (0.5*balloon_parameters['drag_coefficient']*air_density*np.pi*(launch_radius)**2)) # ascent velocity in m/s
    return free_lift, ascent_velocity, burst_height
