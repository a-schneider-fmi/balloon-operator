#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for parachute module.

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
from balloon_operator import parachute

def test_lookupParachuteParameters(verbose=False):
    """
    Unit test for lookupParachuteParameters
    """
    parachute_parameter_list = parachute.readParachuteParameterList('parachute_parameters.tsv')
    if verbose: print(parachute_parameter_list)
    parameters = parachute.lookupParachuteParameters(parachute_parameter_list, 'Totex large')
    assert(parameters['name'] == 'Totex large')
    assert(parameters['diameter'] == 3.9)
    assert(parameters['drag_coefficient'] == 1.5)


def test_parachuteDescent(verbose=False, plot=False):
    """
    Unit test for parachuteDescent
    """
    parachute_name = 'Totex large'
    payload_weight = 5. # kg
    payload_area = 0.07 # m^2
    payload_drag_coefficient = 0.25
    timestep = 10 # s
    alt_start = 30000. # m
    reference_altitude = np.array([30000,29857,29693,29531,29371,29213,29056,28901,28748,28596,28446,28297,28150,28004,27860,27717,27575,27435,27296,27159,27023,26888,26754,26622,26491,26361,26232,26104,25977,25852,25727,25604,25481,25360,25240,25120,25002,24884,24768,24652,24538,24424,24311,24199,24088,23977,23868,23759,23651,23544,23438,23333,23228,23124,23021,22918,22816,22715,22615,22515,22416,22318,22220,22123,22026,21931,21835,21741,21647,21554,21461,21369,21277,21186,21096,21006,20917,20828,20740,20652,20565,20478,20392,20306,20221,20137,20053,19969,19886,19803,19721,19639,19558,19477,19396,19316,19237,19158,19079,19001,18923,18846,18769,18692,18616,18540,18465,18390,18315,18241,18167,18093,18020,17947,17875,17803,17731,17660,17589,17518,17448,17378,17308,17239,17170,17102,17033,16965,16898,16830,16763,16696,16630,16564,16498,16432,16367,16302,16237,16173,16109,16045,15982,15918,15855,15793,15730,15668,15606,15544,15483,15422,15361,15300,15240,15180,15120,15060,15001,14942,14883,14824,14766,14708,14650,14592,14534,14477,14420,14363,14306,14250,14194,14138,14082,14027,13971,13916,13861,13807,13752,13698,13644,13590,13536,13483,13429,13376,13323,13271,13218,13166,13114,13062,13010,12958,12907,12856,12805,12754,12703,12652,12602,12552,12502,12452,12402,12353,12304,12255,12206,12157,12108,12060,12011,11963,11915,11867,11819,11772,11725,11677,11630,11583,11536,11490,11443,11397,11351,11305,11259,11213,11168,11122,11077,11032,10987,10942,10897,10852,10808,10763,10719,10675,10631,10587,10544,10500,10457,10413,10370,10327,10284,10241,10199,10156,10114,10071,10029,9987.2,9945.3,9903.5,9861.8,9820.2,9778.8,9737.5,9696.3,9655.2,9614.2,9573.3,9532.6,9491.9,9451.4,9411,9370.7,9330.5,9290.4,9250.4,9210.6,9170.8,9131.2,9091.7,9052.2,9012.9,8973.7,8934.6,8895.6,8856.7,8817.9,8779.2,8740.6,8702.1,8663.7,8625.4,8587.3,8549.2,8511.2,8473.3,8435.5,8397.8,8360.2,8322.7,8285.3,8248,8210.8,8173.7,8136.7,8099.8,8062.9,8026.2,7989.6,7953,7916.5,7880.2,7843.9,7807.7,7771.6,7735.6,7699.7,7663.8,7628.1,7592.4,7556.9,7521.4,7486,7450.7,7415.5,7380.3,7345.3,7310.3,7275.4,7240.6,7205.9,7171.2,7136.7,7102.2,7067.8,7033.5,6999.3,6965.1,6931.1,6897.1,6863.2,6829.3,6795.6,6761.9,6728.3,6694.8,6661.3,6628,6594.7,6561.5,6528.3,6495.3,6462.3,6429.4,6396.5,6363.8,6331.1,6298.4,6265.9,6233.4,6201,6168.7,6136.4,6104.3,6072.1,6040.1,6008.1,5976.2,5944.4,5912.6,5880.9,5849.3,5817.8,5786.3,5754.8,5723.5,5692.2,5661,5629.8,5598.8,5567.7,5536.8,5505.9,5475.1,5444.3,5413.6,5383,5352.4,5321.9,5291.5,5261.1,5230.8,5200.6,5170.4,5140.3,5110.2,5080.2,5050.3,5020.4,4990.6,4960.9,4931.2,4901.6,4872,4842.5,4813,4783.6,4754.3,4725,4695.8,4666.7,4637.6,4608.5,4579.6,4550.6,4521.8,4493,4464.2,4435.5,4406.9,4378.3,4349.8,4321.3,4292.9,4264.6,4236.3,4208,4179.8,4151.7,4123.6,4095.6,4067.6,4039.7,4011.8,3984,3956.2,3928.5,3900.9,3873.3,3845.7,3818.2,3790.8,3763.4,3736,3708.7,3681.5,3654.3,3627.1,3600.1,3573,3546,3519.1,3492.2,3465.4,3438.6,3411.8,3385.1,3358.5,3331.9,3305.4,3278.9,3252.4,3226,3199.7,3173.3,3147.1,3120.9,3094.7,3068.6,3042.5,3016.5,2990.5,2964.6,2938.7,2912.9,2887.1,2861.3,2835.6,2810,2784.4,2758.8,2733.3,2707.8,2682.4,2657,2631.6,2606.3,2581.1,2555.9,2530.7,2505.6,2480.5,2455.5,2430.5,2405.5,2380.6,2355.7,2330.9,2306.1,2281.4,2256.7,2232,2207.4,2182.9,2158.3,2133.8,2109.4,2085,2060.6,2036.3,2012,1987.8,1963.5,1939.4,1915.3,1891.2,1867.1,1843.1,1819.2,1795.2,1771.3,1747.5,1723.7,1699.9,1676.2,1652.5,1628.8,1605.2,1581.7,1558.1,1534.6,1511.2,1487.7,1464.3,1441,1417.7,1394.4,1371.2,1348,1324.8,1301.7,1278.6,1255.5,1232.5,1209.5,1186.6,1163.7,1140.8,1118,1095.2,1072.4,1049.7,1027,1004.3,981.7,959.11,936.56,914.04,891.56,869.11,846.7,824.32,801.97,779.66,757.38,735.14,712.93,690.76,668.62,646.51,624.43,602.39,580.39,558.41,536.47,514.56,492.69,470.85,449.04,427.26,405.52,383.81,362.13,340.48,318.87,297.28,275.73,254.21,232.73,211.27,189.85,168.46,147.09,125.77,104.47,83.2,61.964,40.759,19.585,0.13162])
    eps_limit = 5e-2
    parachute_parameter_list = parachute.readParachuteParameterList('parachute_parameters.tsv')
    parachute_parameters = parachute.lookupParachuteParameters(parachute_parameter_list, parachute_name)
    time, altitude, velocity = parachute.parachuteDescent(
            alt_start, timestep, payload_weight, parachute_parameters, 
            payload_area, payload_drag_coefficient)
    diff_alt = altitude - reference_altitude
    eps_alt = (altitude - reference_altitude)/reference_altitude
    if plot:
        from matplotlib import pyplot as plt
        plt.figure()
        plt.subplot(3,1,1)
        plt.plot(time, reference_altitude, label='Reference')
        plt.plot(time, altitude, label='This computation')
        plt.ylabel('Altitude (m)')
        plt.legend()
        plt.subplot(3,1,2)
        plt.plot(time, diff_alt)
        plt.ylabel('Difference altitude (m)')
        plt.subplot(3,1,3)
        plt.plot(time, eps_alt)
        plt.ylabel('Relative difference altitude (%)')
        plt.xlabel('Time (s)')
        plt.show()
    # Disregard last values near 0 m altitude in the relative comparison
    # since small absolute errors can mean large relative errors.
    if verbose:
        print('Maximum difference: {:.2f} m, {:.2f} %'.format(np.max(np.abs(diff_alt)), np.max(np.abs(eps_alt[:-25]))*100.))
    assert(np.abs(eps_alt)[:-25] < eps_limit).all()


if __name__ == "__main__":
    test_lookupParachuteParameters(verbose=True)
    test_parachuteDescent(verbose=True, plot=False)
