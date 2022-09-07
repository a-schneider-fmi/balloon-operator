#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module to compute the filling of the balloon.

The computation is based on the "Totex Balloon Burst Estimator" spreadsheet
and on Jens Söder's BalloonTrajectory MATLAB program.

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

import numpy as np
from enum import Enum
from balloon_operator import constants


FillGas = Enum('FillGas', 'HYDROGEN HELIUM')
fill_gas_names = {FillGas.HYDROGEN: 'hydrogen', FillGas.HELIUM: 'helium'}
gas_density = {FillGas.HYDROGEN: 0.0899, FillGas.HELIUM: 0.1786} # gas density in kg/m^3 at STP (standard temperature and pressure, 0°C and 101kPa)

def fillGas(name):
    """
    Gets FillGas enum for name.

    @param name name of the gas ('hydrogen' or 'helium')

    @return FillGas enum
    """
    for fill_gas in FillGas:
        if name.lower() == fill_gas_names[fill_gas]:
            return fill_gas
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


def lookupParameters(parameter_list, name, key='weight'):
    """
    Look up parameters for a given name (e.g. balloon weight).

    @param parameter_list parameter table as named array, e.g. as read with readBalloonParameterList
    @param name name (e.g. balloon weight) to look up the data
    @param key key to use for look-up (default: weight)

    @return selected column of the named array, or None if the given weight is not in the list.
    """
    ind = np.where(parameter_list[:][key] == name)[0]
    if len(ind) != 1:
        return None
    else:
        return parameter_list[ind[0]]


def balloonPerformance(balloon_parameters, payload_weight, launch_volume=None, launch_radius=None, fill_gas=FillGas.HELIUM, burst_height_correction_factor=1.0):
    """
    Compute balloon performance (ascent velocity, burst altitude) based on
    filling and payload weight.
    This is a re-implementation of the Totex Balloon Burst Estimator spreadsheet.

    @param balloon_parameters: named array or dictionary with keys 'weight', 'burst_diameter' and 'drag_coefficient'
    @param payload_weight payload weight in kg
    @param launch_volume fill volume in m^3
    @param launch_radius launch radius corresponding to balloon filling in m, alternative to launch_volume
    @param fill_gas fill gas, instance of FillGas enum
    @param burst_height_correction_factor correction factor for burst height estimation (default: 1.0)

    @return neutral_lift neutral lift in kg
    @return ascent_velocity ascent velocity in m/s (negative for descent)
    @return burst_height burst altitude in m
    """
    assert(launch_volume is not None or launch_radius is not None)
    air_density_model = 7238.3 # air density model from spread sheet
    if launch_radius is None: # if launch radius is not given, but launch volume
        launch_radius = (launch_volume/(4./3.*np.pi))**(1./3.)
    elif launch_volume is None: # if launch volume is not given, but launch radius
        launch_volume = 4./3.*np.pi*launch_radius**3
    burst_volume = 4./3.*np.pi*(balloon_parameters['burst_diameter']/2.)**3 # burst colume in m^3
    burst_height = -air_density_model*np.log(launch_volume/burst_volume) # burst height in m
    gross_lift = launch_volume*(constants.density['air']-gas_density[fill_gas]) # gross lift in kg
    free_lift = gross_lift - (balloon_parameters['weight']/1000. + payload_weight) # free lift in kg
    free_lift_force = free_lift * constants.gravity
    ascent_velocity = np.sign(free_lift_force)*np.sqrt(np.abs(free_lift_force) / (0.5*balloon_parameters['drag_coefficient']*constants.density['air']*np.pi*(launch_radius)**2)) # ascent velocity in m/s
    neutral_lift = payload_weight + free_lift
    burst_height *= burst_height_correction_factor
    return neutral_lift, ascent_velocity, burst_height


def balloonFilling(balloon_parameters, payload_weight, ascent_velocity, fill_gas=FillGas.HELIUM, burst_height_correction_factor=1.0):
    """
    Compute balloon filling for selected ascent rate.

    This uses a bi-section method with the filling performance as forward model.
    Approach from Jens Söder's MATLAB code.

    @param balloon_parameters: named array or dictionary with keys 'weight', 'burst_diameter' and 'drag_coefficient'
    @param payload_weight payload weight in kg
    @param ascent_velocity desired ascent velocity (may be negative for descent)
    @param fill_gas fill gas, instance of FillGas enum
    @param burst_height_correction_factor correction factor for burst height estimation (default: 1.0)

    @return launch_radius launch radius in m
    @return neutral_lift neutral lift in kg
    @return burst_height burst altitude in m
    """
    r_min = 0.
    r_max = 3.
    epsilon = 1e-2
    for i_loop in range(100):
        launch_radius = (r_min+r_max)/2.
        this_neutral_lift, this_ascent_velocity, this_burst_height = balloonPerformance(
                balloon_parameters, payload_weight, launch_radius=launch_radius,
                fill_gas=fill_gas, burst_height_correction_factor=burst_height_correction_factor)
        if np.abs(this_ascent_velocity - ascent_velocity) < epsilon:
            break
        elif this_ascent_velocity > ascent_velocity:
            r_max = launch_radius
        elif this_ascent_velocity < ascent_velocity:
            r_min = launch_radius
    if i_loop == 99:
        raise ValueError('Bisection in balloonFilling did not terminate. Possibly ascent rate is out of bounds.')
    return launch_radius, this_neutral_lift, this_burst_height


def twoBalloonFilling(
        asc_balloon_parameters, desc_balloon_parameters, payload_weight, 
        ascent_velocity, descent_velocity, fill_gas=FillGas.HELIUM, 
        burst_height_correction_factor=1.0):
    """
    Compute balloon filling for two-balloon method for selected ascent and descent rate.
    Approach from Jens Söder's MATLAB code.

    @param asc_balloon_parameters: balloon parameters for ascent balloon from lookupParameters
    @param desc_balloon_parameters: balloon parameters for ascent balloon from lookupParameters
    @param payload_weight payload weight in kg
    @param ascent_velocity desired ascent velocity
    @param descent_velocity desired descent velocity, has to be negative
    @param fill_gas fill gas, instance of FillGas enum
    @param burst_height_correction_factor correction factor for burst height estimation (default: 1.0)

    @return asc_launch_radius launch radius of ascent balloon in m
    @return desc_launch_radius launch radius of descent balloon in m
    @return asc_neutral_lift neutral lift of ascent balloon in kg
    @return desc_neutral_lift neutral lift of descent balloon in kg
    @return asc_burst_height burst altitude of ascent balloon in m
    @return desc_burst_height burst altitude of descent balloon in m
    """
    # First get filling of descent balloon.
    desc_launch_radius, desc_neutral_lift, desc_burst_height = balloonFilling(
            desc_balloon_parameters, payload_weight, -descent_velocity, fill_gas=fill_gas,
            burst_height_correction_factor=burst_height_correction_factor)
    # Now compute the virtual payload weight that the descent balloon would lift
    # with the selected ascent velocity. This is the payload reduction for the
    # ascent balloon.
    # Use bisection method similar as in balloonFilling but optimize payload weight.
    payload_min = -0.5 # Payload reduction may be negative in case of small payload/ large descent balloon.
    payload_max = payload_weight
    epsilon = 1e-2
    for i_loop in range(100):
        this_payload_weight = (payload_min+payload_max)/2.
        this_neutral_lift, this_ascent_velocity, this_burst_height = balloonPerformance(
                desc_balloon_parameters, this_payload_weight, launch_radius=desc_launch_radius, 
                fill_gas=fill_gas, burst_height_correction_factor=burst_height_correction_factor)
        if np.abs(this_ascent_velocity - ascent_velocity) < epsilon:
            break
        elif this_ascent_velocity > ascent_velocity:
            payload_min = this_payload_weight
        elif this_ascent_velocity < ascent_velocity:
            payload_max = this_payload_weight
    if i_loop == 99:
        raise ValueError('Bisection in twoBalloonFilling did not terminate. Possibly descent rate or ascent rate out of bounds or descent balloon too large for payload.')
    # Finally compute the filling of the ascent balloon.
    asc_launch_radius, asc_neutral_lift, asc_burst_height = balloonFilling(
            asc_balloon_parameters, payload_weight-this_payload_weight, ascent_velocity,
            fill_gas=fill_gas, burst_height_correction_factor=burst_height_correction_factor)
    return asc_launch_radius, desc_launch_radius, asc_neutral_lift, desc_neutral_lift, asc_burst_height, desc_burst_height


def main(balloon_weight, payload_weight, launch_radius, ascent_velocity=None,
         fill_gas=FillGas.HELIUM, burst_height_correction_factor=1.0,
         parameter_file='totex_balloon_parameters.tsv'):
    """
    Main function to calculate balloon performance from command line.
    """
    balloon_parameter_list = readBalloonParameterList(parameter_file)
    balloon_parameters = lookupParameters(balloon_parameter_list, balloon_weight)
    if ascent_velocity is None:
        neutral_lift, ascent_velocity, burst_height = balloonPerformance(
                balloon_parameters, payload_weight, launch_radius=launch_radius,
                fill_gas=fill_gas, burst_height_correction_factor=burst_height_correction_factor)
        print('Neutral lift {:.3f} kg, ascent velocity {:.1f} m/s, burst height {:.0f} m'.format(neutral_lift, ascent_velocity, burst_height))
    else:
        launch_radius, neutral_lift, burst_height = balloonFilling(
                balloon_parameters, payload_weight, ascent_velocity, fill_gas=fill_gas,
                burst_height_correction_factor=burst_height_correction_factor)
        print('Fill radius {:.3f} m, fill volume {:.2f} m^3, neutral lift: {} kg, burst altitude: {:.0f} m'.format(
                launch_radius, 4./3.*np.pi*launch_radius**3, neutral_lift, burst_height))
    return


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser('Balloon filling computation')
    parser.add_argument('balloon', type=int, help='Balloon type (weight in g)')
    parser.add_argument('payload', type=float, help='Payload weight in kg')
    parser.add_argument('radius', type=float, help='Launch radius in m')
    parser.add_argument('-v', '--velocity', required=False, type=int, default=None, help='Ascent velocity in m/s')
    parser.add_argument('-g', '--gas', required=False, default='helium', help='Fill gas (hydrogen or helium)')
    parser.add_argument('-c', '--correction-factor', required=False, type=float, default=1.0, help='Burst height correction factor')
    args = parser.parse_args()
    main(args.balloon, args.payload, args.radius, ascent_velocity=args.velocity, fill_gas=fillGas(args.gas), burst_height_correction_factor=args.correction_factor)
