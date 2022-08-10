# Balloon Operator

Balloon operation software including trajectory prediction and flight control

Balloon Operator is based on the BalloonTrajectory MATLAB software that has
been developed by Jens Söder <soeder@iap-kborn.de> at the Institute of
Atmospheric Physics in Kühlungsborn.


## Features

* Compute trajectories of balloon flights
    * Single forecast
    * Hourly forecasts
    * Live forecast to predict the continuation of an ongoing flight based on received coordinates
* Export trajectories in GPX or KML format or as a webpage and optionally upload them to a server
* Communication with payload via
    * IRIDIUM SBD messages from/to a RockBLOCK device
    * a local file modified by an external program
* Send messages to a balloon e.g. to activate a cutter
* Graphical user interface


## Author

Balloon Operator is written by Andreas Schneider <andreas.schneider@fmi.fi>
at the Finnish Meteorological Institute in Sodankylä.


## License

Balloon Operator is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.

Balloon Operator is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

A copy of the GNU General Public License can be found in the file LICENSE.md.
Alternatively, see <https://www.gnu.org/licenses/>.


## Dependencies

This software uses the Python Standard Library (e.g. packages datetime, os.path,
pathlib, sys, enum, configparser, argparse) and the following third-party packages:
* [numpy](http://www.numpy.org)
* [scipy](http://www.scipy.org)
* [requests](http://python-requests.org)
* [pygrib](https://github.com/jswhit/pygrib)
* [geog](https://github.com/jwass/geog)
* [gpxpy](https://github.com/tkrajina/gpxpy)
* [srtm-python](https://github.com/aatishnn/srtm-python)
* [simplekml](https://github.com/eisoldt/simplekml)
* [cfgrib](https://github.com/ecmwf/cfgrib) for using HARMONIE model data
* [paramiko](https://github.com/paramiko/paramiko) for uploading data with scp/sftp
* [folium](https://github.com/python-visualization/folium) for creating web pages
* [pyside6](https://doc.qt.io/qtforpython/) for the graphical user interface
* [matplotlib](https://www.matplotlib.org/) for live plots
* [cartopy](https://scitools.org.uk/cartopy/docs/latest/) for exporting a map with the trajectory
* [countries](https://github.com/che0/countries) if boundary crossing shall be determined
* [gdal](https://gdal.org/) as dependency for `countries`

Usually, these can be installed with `pip`:
```
pip install numpy scipy requests pygrib geog gpxpy simplekml
```
and if needed
```
pip install folium
pip install paramiko
pip install pyside6
pip install matplotlib
pip install cartopy
pip install gdal
```
The packages `srtm-python` and `countries` are not available in pypi and have to
be cloned from github (don't forget to set the PYTHONPATH so that they are found).

With the [Anaconda](https://www.anaconda.com/) Python distribution, packages
are installed with `conda`, but some are not available in the standard channel.
Thus:
```
conda update --all
conda install numpy scipy requests
conda install -c conda-forge gpxpy simplekml pygrib
pip install geog
```
and if needed
```
conda install -c conda-forge folium
conda install -c conda-forge paramiko
pip install pyside6
conda install matplotlib
conda install cartopy
conda install gdal
```
On Windows, if you encounter an error message like
```
qt.qpa.plugin: Could not find the Qt platform plugin "windows" in ""
This application failed to start because no Qt platform plugin could be initialized. Reinstalling the application may fix this problem.
```
the solution is to tell Python where to find it via the environment variable
`QT_QPA_PLATFORM_PLUGIN_PATH`, e.g.
```
set QT_QPA_PLATFORM_PLUGIN_PATH=C:\ProgramData\Anaconda3\Lib\site-packages\PySide6\plugins
```
in the command line, or set the environment variable in the system settings.
Please note that the path can vary with your installation.

On Linux, it is advisable to install Python packages through the system's
packaging system. On Debian-based distributions (e.g. Ubuntu), the command is
```
sudo apt install python3-numpy python3-scipy python3-requests python3-grib python3-gpxpy
```
and if needed
```
sudo apt install python3-matplotlib python3-cartopy python3-gdal
```
Some Python packages are not available through the Linux packaging system.
These can either be installed with pip or by cloning the repositories and setting
the PYTHONPATH.


## Installation

Clone the source from the repository. If you want to run the graphical user
interface, you have to compile some files. To do so, go into the
`balloon_operator` directory and run `make_gui.bat`. This needs
[Inkscape](https://inkscape.org/) to convert the app icon and Pyside6 (see
above under Dependencies) to compile the UI.


## Data
* To compute a balloon trajectory, the software automatically downloads recent
  GFS model data from NOAA.
* To compute the landing, a digital elevation model (DEM) is used. Data has to
  be downloaded manually from http://viewfinderpanoramas.org/dem3.html; the
  `HGT_DIR` environment variable should point to the location of the unpacked data.
* To determine border crossings, the
  [World Borders Dataset](http://thematicmapping.org/downloads/world_borders.php)
  needs to be available. The `WORLD_BORDERS_FILE` environment variable should point
  to the location of the file `TM_WORLD_BORDERS-0.3.shp`.


## Graphical user interface

A graphical user interface exposing almost all functionality is `operator_gui.py`.
Data can be pre-loaded with command-line arguments:

* `-p payload_config_file` (long name `--payload`): load payload configuration from ini file
* `-c comm_config_file` (long name `--config`): load communication configuration from ini file
* `-b balloon_param.ini` (long name `--balloon-param`): balloon parameter file (default `totex_balloon_parameters.tsv`)
* `--parachute-param parachute_param.ini`: parachute parameter file (default `parachute_parameters.tsv`)

The main window supports balloon performance computations and trajectory forecasts.

A second window for live operations can be opened with a button. The payload
status from messages is shown, a new trajectory estimation is computed each time
a new message arrives, and messages can be sent to the payload, e.g. to trigger
cutters.

Support for displaying custom payload-specific data exists. To this end, a
widget named `gui_payloadwidget_name.ui` and a matching Python module
`payloadwidget_name.py` are needed, where `name` has to be replaced with the
actual payload name. The Python module needs to have a method
`setPayloadData(payload_widget, data)`
This method will be called by `OperatorWidget` when a new message arrives with
the widget instance from QUiLoader as first parameter and the message as second
parameter. See `gui_payloadwidget_wifvos.ui` and `payloadwidget_wifvos.py` for
an example.


## Command-line tools

### Trajectory predictor

A command-line program to predict balloon trajectories.

Arguments:
* launch time in format YY-MM-DD HH:MM (space needs to be escaped from the shell)
* `-i config_file` : use configuration from `config_file` (default: `flight.ini`)
* `-p lon,lat,alt` : overwrite launch position in format lon,lat,alt
* `-d` : compute descent only
* `-t [duration]` : compute hourly prediction for `duration` hours
* `-l comm.ini` : do live forcast receiving current location as specified in comm.ini
* `-k [networklink]`: output result in KML format instead of GPX, optionally adding a network link
* `-w webpage_filename` : create an HTML + JavaScript web page and write it to given file
* `-u comm.ini` : upload results to web server
* `-o output_filename` : write output in file `output_filename`
* `--log` : set verbosity (CRITICAL, ERROR, WARNING, INFO, DEBUG), default INFO

### SBD message translator and sender/receiver `message_sbd`

A command-line program to decode and encode binary SBD messages and optionally
receive/send from/to a mobile device.

Arguments:

* `-r config.ini` : retrieve messages via IMAP as specified in configuration file
* `-a` : retrieve all messages, not only unread ones
* `-o filename` : output file for encoded binary message or GPX track from decoded message(s)
* `-c` : write out time, coordinates and optional data in CSV format
* `-d` : decode binary message given as hex string
* `-e` : encode binary message
* `-p lon,lat,alt` : include given position in encoded message
* `-t [YY-mm-ddTHH:MM:SS]` : include time in encoded message (now if no time specified)
* `-u n[,m]` : include userfunction(s) in message, where the argument is a comma-separated list of digits between 1 and 8
* `-s tracker.ini` : send message to device specified in given ini file

The ini file for retrieving should include an `email` section as described below
under communications configuration file.

The ini file for sending should have the following entries:
* option in section `device`:
    * `imei`: The unique IMEI of the RockBLOCK to send to
* options in section `rockblock`:
    * `user`: Rock 7 Core username
    * `password`: Rock 7 Core password
This is also compatible with the structure of the communication ini file.


## File formats

### Flight configuration file

An example is included in `flight.ini`. The configuration file contains:
* options in section `launch_site`:
    * `longitude`: launch longitude
    * `latitude`: launch latitude
    * `altitude`: launch altitude
* options in section `payload`:
    * `payload_weight`: payload weight in kg
    * `payload_area`: downward-facing payload area in m^2
    * `ascent_balloon_weight`: weight of ascent balloon in g (balloon type)
    * `descent_balloon_weight`: weight of descent balloon in g (balloon type)
    * `fill_gas`: gas to be filled into the balloon (`hydrogen` or `helium`)
    * `ascent_velocity`: desired ascent velocity in m/s
    * `cut_altitude`: altitude in m in which the ascent balloon shall be cut; if not specified, burst altitude is calculated
    * `descent_velocity`: desired descent velocity for two-balloon flight; if not specified, a normal one-balloon flight with descent on parachute is assumed
    * `parachute_type`: desired parachute type
* options in section `parameters`:
    * `balloon`: name of tsv file with balloon parameters, e.g. `totex_balloon_parameters.tsv`
    * `parachute`: name of tsv file with parachute parameters, e.g. `parachute_parameters.tsv`
    * `timestep` time step for simulation in s
    * `model_path`: directory to which model data shall be downloaded

### Communications configuration file

An example is included in `comm.ini`. The configuration contains:
* options in section `connection`:
    * `type`:  type of connection to balloon, currently implemented options:
        * `rockblock`: RockBLOCK service using SBD messages via IRIDIUM satellite link
        * `file`: read data from local file
    * `poll_time`: Time interval in seconds to poll for new messages (default: 30)
      Can also be selected in the GUI.
* options in section `email`:
    * `host`: hostname to query mails with SBD messages via IMAP
    * `user`: username for IMAP
    * `password`: password for IMAP
    * `from`: from address to be filtered for, e.g. `300123456789012@rockblock.rock7.com`
* options in section `rockblock`:
    * `user`: username at Rock 7 Core (used to send messages to devices)
    * `password`: password at Rock 7 Core (used to send messages to devices)
* options in section `rockblock_devices`:
    * Provide a list of RockBLOCK devices in the format `Name = imei`
* options in section `file`:
    * `path`: path to the csv file to read data from
    * `delimiter`: delimiter of the csv file (default: '\t' (tab))
* options in section `webserver`:
    * `protocol`: protocol by which to upload data to webserver, `ftp`, `sftp` or `post`
    * `host`: hostname on which to upload results (or upload URL for post method)
    * `user`: username with which to login (FTP and SFTP)
    * `password`: password (FTP and SFTP) or access token (post)
    * `directory`: (remote) directory to which to upload resulting files
    * `webpage`: file name for generated HTML file
    * `networklink`: URL for network link to include in KML file
    * `refreshinterval`: refresh interval for KML network link in seconds
* options in section `output`:
    * `format`: format in which to create output files, `gpx` or `kml`
    * `filename`: output file name for (GPX or KML) trajectory
    * `directory`: (local) directory to which to write the resulting files
* options in section `geofence`: in order to filter erroneous position messages
  during life forecast, a circular geofence can be lain around the launch position.
    * `radius`: radius of the circle around the launch point in km

### Balloon parameter TSV file

A file in tab separated value format with balloon parameters containing the
three columns balloon weight (in g), burst diameter (in m), and drag coefficient.
The first line is treated as header line.

### Parachute parameter TSV file

A file in tab separated value format with parachute parameters containing the
three columns parachute name, diameter (in m), and drag coefficient.
The first line is treated as header line.
