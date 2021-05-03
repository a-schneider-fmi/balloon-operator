# Balloon Operator

Balloon operation software including trajectory prediction and flight control

This software package is based on the BalloonTrajectory MATLAB software which
has been developed by Jens Söder <soeder@iap-kborn.de> at the Institute of 
Atmospheric Physics in Kühlungsborn.


## Dependencies

This software uses the Python Standard Library (e.g. packages datetime, os.path,
pathlib, sys, enum, configparser, argparse) and the following third-party packages:
* [numpy](http://www.numpy.org)
* [scipy](http://www.scipy.org)
* [requests](http://python-requests.org)
* [pygrib](https://github.com/jswhit/pygrib)
* [magic](https://github.com/ahupp/python-magic)
* [geog](https://github.com/jwass/geog)
* [gpxpy](https://github.com/tkrajina/gpxpy)
* [srtm-python](https://github.com/aatishnn/srtm-python)


## Data
* To compute a balloon trajectory, the software automatically downloads recent
  GFS model data from NOAA.
* To compute the landing, a digital elevation model (DEM) is used. Data has to
  be downloaded manually from http://viewfinderpanoramas.org/dem3.html; the
  HGT_DIR environment variable should point to the location of the unpacked data.
