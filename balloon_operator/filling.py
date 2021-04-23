#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute filling of the balloon.

The computation is based on the "Totex Balloon Burst Estimator" spreadsheet
and on Jens Söder's BalloonTrajectory MATLAB program.

Created on Thu Apr  8 07:38:26 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import numpy as np
from enum import Enum

FillGas = Enum('FillGas', 'HYDROGEN HELIUM')
gas_density = {FillGas.HYDROGEN: 0.0899, FillGas.HELIUM: 0.1786} # gas density in kg/m^3 at STP (standard temperature and pressure, 0°C and 101kPa)

def fillGas(name):
    """
    Gets FillGas enum for name.

    @param name name of the gas ('hydrogen' or 'helium')
    @return FillGas enum
    """
    if name.lower() == 'hydrogen':
        return FillGas.HYDROGEN
    elif name.lower() == 'helium':
        return FillGas.HELIUM
    else:
        raise ValueError('Unknown fill gas: {}'.format(name))


def readBalloonParameterList(filename):
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

    @param balloon_parameters balloon parameter table as read with readBalloonParameterList
    @param balloon_weight balloon weight to look up the data
    @return named array with keys 'weight', 'burst_diameter' and 'drag_coefficient', or None if the given weight is not in the list.
    """
    ind = np.where(balloon_parameter_list[:]['weight'] == balloon_weight)[0]
    if len(ind) != 1:
        return None
    else:
        return balloon_parameter_list[ind[0]]


def balloonPerformance(balloon_parameters, payload_weight, launch_volume=None, launch_radius=None, fill_gas=FillGas.HELIUM, burst_height_correction=False):
    """
    Compute balloon performance (ascent velocity, burst altitude) based on
    filling and payload weight.
    This is a re-implementation of the Totex Balloon Burst Estimator spreadsheet.

    @param balloon_parameters: named array or dictionary with keys 'weight', 'burst_diameter' and 'drag_coefficient'
    @param payload_weight payload weight in kg
    @param launch_volume fill volume in m^3
    @param launch_radius launch radius corresponding to balloon filling in m, alternative to launch_volume
    @param fill_gas fill gas, instance of FillGas enum
    @return free_lift free lift in kg
    @return ascent_velocity ascent velocity in m/s (negative for descent)
    @return burst_height burst altitude in m
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
    if burst_height_correction:
        burst_height *= 1.03 # Correct underestimation of burst height by 3%.
    return free_lift, ascent_velocity, burst_height


def balloonFilling(balloon_parameters, payload_weight, ascent_velocity, fill_gas=FillGas.HELIUM, burst_height_correction=True):
    """
    Compute balloon filling for selected ascent rate.

    This uses a bi-section method with the filling performance as forward model.
    Approach from Jens Söder's MATLAB code.

    @param balloon_parameters: named array or dictionary with keys 'weight', 'burst_diameter' and 'drag_coefficient'
    @param payload_weight payload weight in kg
    @param ascent_velocity desired ascent velocity (may be negative for descent)
    @return launch_radius launch radius in m
    @return free_lift free lift in kg
    @return burst_height burst altitude in m
    """
    r_min = 0.
    r_max = 3.
    epsilon = 1e-2
    for i_loop in range(100):
        launch_radius = (r_min+r_max)/2.
        this_free_lift, this_ascent_velocity, this_burst_height = balloonPerformance(
                balloon_parameters, payload_weight, launch_radius=launch_radius,
                fill_gas=fill_gas, burst_height_correction=burst_height_correction)
        if np.abs(this_ascent_velocity - ascent_velocity) < epsilon:
            break
        elif this_ascent_velocity > ascent_velocity:
            r_max = launch_radius
        elif this_ascent_velocity < ascent_velocity:
            r_min = launch_radius
    if i_loop == 99:
        raise ValueError('Bisection in balloonFilling did not terminate. Possibly ascent rate is out of bounds.')
    return launch_radius, this_free_lift, this_burst_height


def twoBalloonFilling(
        asc_balloon_parameters, desc_balloon_parameters, payload_weight, 
        ascent_velocity, descent_velocity, fill_gas=FillGas.HELIUM, 
        burst_height_correction=True):
    """
    Compute balloon filling for two-balloon method for selected ascent and descent rate.

    Approach from Jens Söder's MATLAB code.

    @param asc_balloon_parameters: balloon parameters for ascent balloon from lookupBalloonParameters
    @param desc_balloon_parameters: balloon parameters for ascent balloon from lookupBalloonParameters
    @param payload_weight payload weight in kg
    @param ascent_velocity desired ascent velocity
    @param descent_velocity desired descent velocity, has to be negative
    @return asc_launch_radius launch radius of ascent balloon in m
    @return desc_launch_radius launch radius of descent balloon in m
    @return asc_free_lift free lift of ascent balloon in kg
    @return desc_free_lift free lift of descent balloon in kg
    @return payload_reduction reduction of payload due to descent balloon during ascent in kg
    @return asc_burst_height burst altitude of ascent balloon in m
    @return desc_burst_height burst altitude of descent balloon in m
    """
    # First get filling of descent balloon.
    desc_launch_radius, desc_free_lift, desc_burst_height = balloonFilling(
            desc_balloon_parameters, payload_weight, descent_velocity, fill_gas=fill_gas,
            burst_height_correction=burst_height_correction)
    # Now compute the virtual payload weight that the descent balloon would lift
    # with the selected ascent velocity. This is the payload reduction for the
    # ascent balloon.
    # Use bisection method similar as in balloonFilling but optimize payload weight.
    payload_min = -0.5 # Payload reduction may be negative in case of small payload/ large descent balloon.
    payload_max = payload_weight
    epsilon = 1e-2
    for i_loop in range(100):
        this_payload_weight = (payload_min+payload_max)/2.
        this_free_lift, this_ascent_velocity, this_burst_height = balloonPerformance(
                desc_balloon_parameters, this_payload_weight, launch_radius=desc_launch_radius, 
                fill_gas=fill_gas, burst_height_correction=burst_height_correction)
        if np.abs(this_ascent_velocity - ascent_velocity) < epsilon:
            break
        elif this_ascent_velocity > ascent_velocity:
            payload_min = this_payload_weight
        elif this_ascent_velocity < ascent_velocity:
            payload_max = this_payload_weight
    if i_loop == 99:
        raise ValueError('Bisection in twoBalloonFilling did not terminate. Possibly descent rate or ascent rate out of bounds or descent balloon too large for payload.')
    # Finally compute the filling of the ascent balloon.
    asc_launch_radius, asc_free_lift, asc_burst_height = balloonFilling(
            asc_balloon_parameters, payload_weight-this_payload_weight, ascent_velocity,
            fill_gas=fill_gas, burst_height_correction=burst_height_correction)
    return asc_launch_radius, desc_launch_radius, asc_free_lift, desc_free_lift, this_payload_weight, asc_burst_height, desc_burst_height
