#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 16 09:37:51 2021
@author: Andreas Schneider <andreas.schneider@fmi.fi>
"""

from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure

class GuiFigureCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        super(FigureCanvas, self).__init__(fig)
