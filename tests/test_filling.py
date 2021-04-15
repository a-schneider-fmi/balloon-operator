#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for filling.py.

Created on Thu Apr  8 09:50:51 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

import numpy as np
from balloon_operator import filling

def test_lookupBalloonParameters():
    """
    Unit test for lookupBalloonParameters
    """
    balloon_parameter_list = filling.readBalloonParameters('totex_balloon_parameters.csv')
    parameters_800 = filling.lookupBalloonParameters(balloon_parameter_list, 800)
    assert(parameters_800['weight'] == 800)
    assert(parameters_800['burst_diameter'] == 7.)
    assert(parameters_800['drag_coefficient'] == 0.3)


def test_balloonPerformance():
    """
    Unit test for balloonPerformance
    """
    balloon_weight = 800. # g
    payload_weight = 12. # kg
    launch_volume = 16. # m^2
    gas = filling.FillGas.HELIUM
    result_free_lift = 3.6224
    result_ascent_rate = 5.06067163990215
    result_burst_height = 17503
    eps_limit = 1e-5
    balloon_parameter_list = filling.readBalloonParameters('totex_balloon_parameters.csv')
    balloon_parameters = filling.lookupBalloonParameters(balloon_parameter_list, balloon_weight)
    free_lift, ascent_velocity, burst_height = filling.balloonPerformance(
            balloon_parameters, payload_weight, launch_volume, fill_gas=gas)
    eps_free_lift = np.abs(free_lift - result_free_lift)/result_free_lift
    eps_ascent_velocity = np.abs(ascent_velocity - result_ascent_rate)/result_ascent_rate
    eps_burst_height = np.abs(burst_height - result_burst_height)/result_burst_height
    print('Relative difference: free lift {}, ascent velocity {}, burst height {}'.format(eps_free_lift, eps_ascent_velocity, eps_burst_height))
    assert(eps_free_lift < eps_limit)
    assert(eps_ascent_velocity < eps_limit)
    assert(eps_burst_height < eps_limit)
    launch_radius = (launch_volume/(4./3.*np.pi))**(1./3.)
    free_lift_2, ascent_velocity_2, burst_height_2 = filling.balloonPerformance(
            balloon_parameters, payload_weight, launch_radius=launch_radius, fill_gas=gas)
    assert np.abs((free_lift - free_lift_2)/free_lift) < eps_limit, 'Free lift: {} != {}'.format(free_lift, free_lift_2)
    assert np.abs((ascent_velocity - ascent_velocity_2)/ascent_velocity) < eps_limit, 'Ascent velocity: {} != {}'.format(ascent_velocity, ascent_velocity_2)
    assert np.abs((burst_height - burst_height_2)/burst_height) < eps_limit, 'Burst height: {} != {}'.format(burst_height, burst_height_2)


if __name__ == "__main__":
    test_lookupBalloonParameters()
    test_balloonPerformance()
