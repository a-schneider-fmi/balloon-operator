#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for filling.py.

Created on Thu Apr  8 09:50:51 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import numpy as np
from balloon_operator import filling

def test_fillGas():
    """
    Unit test for fillGas
    """
    fill_gas = filling.fillGas('helium')
    assert(fill_gas == filling.FillGas.HELIUM)
    assert(filling.fillGas('hydrogen') == filling.FillGas.HYDROGEN)


def test_lookupParameters():
    """
    Unit test for lookupParameters
    """
    balloon_parameter_list = filling.readBalloonParameterList('totex_balloon_parameters.tsv')
    parameters_800 = filling.lookupParameters(balloon_parameter_list, 800)
    assert(parameters_800['weight'] == 800)
    assert(parameters_800['burst_diameter'] == 7.)
    assert(parameters_800['drag_coefficient'] == 0.3)


def test_balloonPerformance(verbose=False):
    """
    Unit test for balloonPerformance
    """
    balloon_weight = 800. # g
    payload_weight = 12. # kg
    launch_volume = 16. # m^2
    fill_gas = filling.FillGas.HELIUM
    reference_free_lift = 3.6224
    reference_ascent_rate = 5.06067163990215
    reference_burst_height = 17503
    eps_limit = 2e-4
    balloon_parameter_list = filling.readBalloonParameterList('totex_balloon_parameters.tsv')
    balloon_parameters = filling.lookupParameters(balloon_parameter_list, balloon_weight)
    free_lift, ascent_velocity, burst_height = filling.balloonPerformance(
            balloon_parameters, payload_weight, launch_volume, fill_gas=fill_gas,
            burst_height_correction=False)
    if verbose:
        print('balloonPerformance')
        print('Free list: {:.2f} kg, ascent velocity: {:.2f} m/s, burst altitude: {:.0f} m'.format(
                free_lift, ascent_velocity, burst_height))
    eps_free_lift = (free_lift - reference_free_lift)/reference_free_lift
    eps_ascent_velocity = (ascent_velocity - reference_ascent_rate)/reference_ascent_rate
    eps_burst_height = (burst_height - reference_burst_height)/reference_burst_height
    print('Relative difference: free lift {}, ascent velocity {}, burst height {}'.format(eps_free_lift, eps_ascent_velocity, eps_burst_height))
    assert(np.abs(eps_free_lift) < eps_limit)
    assert(np.abs(eps_ascent_velocity) < eps_limit)
    assert(np.abs(eps_burst_height) < eps_limit)
    launch_radius = (launch_volume/(4./3.*np.pi))**(1./3.)
    free_lift_2, ascent_velocity_2, burst_height_2 = filling.balloonPerformance(
            balloon_parameters, payload_weight, launch_radius=launch_radius, fill_gas=fill_gas,
            burst_height_correction=False)
    if verbose:
        print('Free list: {:.2f} kg, ascent velocity: {:.2f} m/s, burst altitude: {:.0f} m'.format(
                free_lift_2, ascent_velocity_2, burst_height_2))
    assert np.abs((free_lift - free_lift_2)/free_lift) < eps_limit, 'Free lift: {} != {}'.format(free_lift, free_lift_2)
    assert np.abs((ascent_velocity - ascent_velocity_2)/ascent_velocity) < eps_limit, 'Ascent velocity: {} != {}'.format(ascent_velocity, ascent_velocity_2)
    assert np.abs((burst_height - burst_height_2)/burst_height) < eps_limit, 'Burst height: {} != {}'.format(burst_height, burst_height_2)


def test_balloonFilling(verbose=False):
    """
    Unit test for balloonFilling
    """
    balloon_parameter_list = filling.readBalloonParameterList('totex_balloon_parameters.tsv')
    # Test filling of ascent balloon.
    balloon_weight = 2000. # g
    payload_weight = 12. # kg
    ascent_velocity = 5. # m/s
    fill_gas = filling.FillGas.HELIUM
    reference_burst_height = 27059 # m
    reference_lift = 15.020 # kg
    reference_launch_radius =  1.5718 # m
    eps_limit = 1e-2
    balloon_parameters = filling.lookupParameters(balloon_parameter_list, balloon_weight)
    launch_radius, free_lift, burst_height = filling.balloonFilling(
            balloon_parameters, payload_weight, ascent_velocity, fill_gas=fill_gas)
    lift = payload_weight + free_lift
    if verbose:
        print('balloonFilling')
        print('Fill radius {:.3f} m, fill volume {:.2f} m^3, burst altitude: {:.0f} m'.format(
                launch_radius, 4./3.*np.pi*launch_radius**3, burst_height))
        print('Lift: {} kg'.format(lift))
    eps_launch_radius = (launch_radius - reference_launch_radius)/reference_launch_radius
    eps_burst_height = (burst_height - reference_burst_height)/reference_burst_height
    eps_lift = (lift - reference_lift)/reference_lift
    if verbose:
        print('Difference: radius {:.3f} %, burst height {:.3f} %, lift {:.3f} %'.format(eps_launch_radius*100., eps_burst_height*100., eps_lift*100.))
    assert (np.abs(eps_launch_radius) < eps_limit), 'Launch radius differs by {:.2f}%.'.format(eps_launch_radius*100.)
    assert (np.abs(eps_burst_height) < eps_limit), 'Burst height differs by {:.2f}%.'.format(eps_burst_height*100.)
    assert (np.abs(eps_lift) < eps_limit), 'Lift differs by {:.2f}%.'.format(eps_lift*100.)
    # Test filling of descent balloon.
    balloon_weight = 2000. # g
    payload_weight = 12. # kg
    ascent_velocity = -5. # m/s
    fill_gas = filling.FillGas.HELIUM
    reference_launch_radius =  1.3850 # m
    balloon_parameters = filling.lookupParameters(balloon_parameter_list, balloon_weight)
    launch_radius, free_lift, burst_height = filling.balloonFilling(
            balloon_parameters, payload_weight, ascent_velocity, fill_gas=fill_gas)
    if verbose:
        print('Fill radius {:.3f} m, fill volume {:.2f} m^3, burst altitude: {:.0f} m'.format(
                launch_radius, 4./3.*np.pi*launch_radius**3, burst_height))
    eps_launch_radius = (launch_radius - reference_launch_radius)/reference_launch_radius
    assert (np.abs(eps_launch_radius) < eps_limit), 'Launch radius differs by {:.2f}%.'.format(eps_launch_radius*100.)


def test_twoBalloonFilling(verbose=False):
    """
    Unit test for twoBalloonFilling
    """
    balloon_parameter_list = filling.readBalloonParameterList('totex_balloon_parameters.tsv')
    asc_balloon_weight = 2000. # g
    desc_balloon_weight = 3000. # g
    payload_weight = 12. # kg
    ascent_velocity = 5. # m/s
    descent_velocity = -5. # m/s
    fill_gas = filling.FillGas.HELIUM
    reference_asc_launch_radius = 1.2664 # m
    reference_desc_launch_radius = 1.4194 # m
    reference_asc_burst_height = 31892 # m
    reference_desc_burst_height = 34031 # m
    reference_asc_lift =  6.9013 # kg
    reference_desc_lift = 9.5352 # kg
    eps_limit = 1e-2
    asc_balloon_parameters = filling.lookupParameters(balloon_parameter_list, asc_balloon_weight)
    desc_balloon_parameters = filling.lookupParameters(balloon_parameter_list, desc_balloon_weight)
    asc_launch_radius, desc_launch_radius, asc_free_lift, desc_free_lift, payload_reduction, asc_burst_height, desc_burst_height = filling.twoBalloonFilling(
            asc_balloon_parameters, desc_balloon_parameters, payload_weight, 
            ascent_velocity, descent_velocity, fill_gas=fill_gas)
    asc_lift = payload_weight - payload_reduction + asc_free_lift
    desc_lift = payload_weight + desc_free_lift
    if verbose:
        print('twoBalloonFilling')
        print('Launch radius: ascent {:.3f} m, descent {:.3f} m'.format(asc_launch_radius, desc_launch_radius))
        print('Burst altitude: ascent balloon {:.0f} m, descent balloon {:.0f} m'.format(asc_burst_height, desc_burst_height))
        print('Lift: ascent balloon {:.3f} kg, descent balloon {:.3f} kg'.format(asc_lift, desc_lift))
    eps_asc_launch_radius = (asc_launch_radius - reference_asc_launch_radius)/reference_asc_launch_radius
    eps_desc_launch_radius = (desc_launch_radius - reference_desc_launch_radius)/reference_desc_launch_radius
    eps_asc_burst_height = (asc_burst_height - reference_asc_burst_height)/reference_asc_burst_height
    eps_desc_burst_height = (desc_burst_height - reference_desc_burst_height)/reference_desc_burst_height
    eps_asc_lift = (asc_lift - reference_asc_lift)/reference_asc_lift
    eps_desc_lift = (desc_lift - reference_desc_lift)/reference_desc_lift
    if verbose:
        print('Difference ascent: radius {:.3f} %, burst height {:.3f} %, lift {:.3f} %'.format(eps_asc_launch_radius*100., eps_asc_burst_height*100., eps_asc_lift*100.))
        print('Difference descent: radius {:.3f} %, burst height {:.3f} %, lift {:.3f} %'.format(eps_desc_launch_radius*100., eps_desc_burst_height*100., eps_desc_lift*100.))
    assert (np.abs(eps_asc_launch_radius) < eps_limit), 'Ascent launch radius differs by {:.2f}%.'.format(eps_asc_launch_radius*100.)
    assert (np.abs(eps_desc_launch_radius) < eps_limit), 'Descent launch radius differs by {:.2f}%.'.format(eps_desc_launch_radius*100.)
    assert (np.abs(eps_asc_burst_height) < eps_limit), 'Ascent burst height differs by {:.2f}%.'.format(eps_asc_burst_height*100.)
    assert (np.abs(eps_desc_burst_height) < eps_limit), 'Descent burst height differs by {:.2f}%.'.format(eps_desc_burst_height*100.)
    assert (np.abs(eps_asc_lift) < eps_limit), 'Ascent lift differs by {:.2f}%.'.format(eps_asc_lift*100.)
    assert (np.abs(eps_desc_lift) < eps_limit), 'Descent lift differs by {:.2f}%.'.format(eps_desc_lift*100.)


if __name__ == "__main__":
    test_fillGas()
    test_lookupParameters()
    test_balloonPerformance(verbose=True)
    test_balloonFilling(verbose=True)
    test_twoBalloonFilling(verbose=True)
