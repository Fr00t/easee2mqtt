## About
This program will transfer data from and control your Easee charging robot via their Dashboard to/from a MQTT-broker of your choice. You can read power usage, current state of the charger and it allows you to start/stop charging and lock/unlock the cable.

Easee has their API documented [here](https://developer.easee.cloud/reference/post_api-accounts-token). There are plenty of endpoints, data and control here. For this program I've selected a few that seems most relevant and useful to me. If you have other needs let me know and I'll see what can be done.


## Prerequisites
Your charging robot needs to be connected to the internet and you need an account on [easee cloud](https://easee.cloud/). You need to have a MQTT-broker and a server, Raspberry Pi or similar with Python installed that can have the program running.


## Installation
This is a Python program and has been developed and tested on Python 3.8. 

1. Download or clone the repository
2. Install necessary packages from requirements.txt using `pip install -r requirements.txt`
3. Run setup.py and follow the instructions to set up and test connections to Easee and broker: `python setup.py` The information is stored **in plain text** locally in the directory in a file named `settings.json`.
   - You will be asked whether the program should run continously and monitor subscribed topics. If all you want is to monitor the charger and not control it is recommended to select `monitor only` in the setup. This will exit the program after each run.
4. Run `easee2mqtt.py`. 
   - If you selected `monitor only` in the previous step you need to run the script on a schedule using cron or similar.
   - If you selected `monitor and control` in the previous step the program will continue to run and monitored the subscribed topics.

## Usage
Below is a list of the published topics with their corresponding units. The program does not support JSON-formatted payloads. 

### Published topics
Each charger identified by the setup script will be monitored every 5 mintues while the script is running. The charger IDs can be found in settings.json after running the script or in their app.

Topic | Content | Unit
--- | --- | ---
easee2MQTT/{charger_ID}/energy_consumption | Accumulated energy usage | kWh
easee2MQTT/{charger_ID}/current_session | Energy usage during current charging session | kWh
easee2MQTT/{charger_ID}/previous_session | Energy usage during previous charging session | kWh
easee2MQTT/{charger_ID}/voltage | Voltage | V
easee2MQTT/{charger_ID}/power | Current power usage | W
easee2MQTT/{charger_ID}/cable_lock | Whether the cable is locked or not | bool
easee2MQTT/{charger_ID}/charging | True if currently charging | bool
easee2MQTT/{charger_ID}/charging_enabled | True if charging is enabled | bool
easee2MQTT/{charger_ID}/charging | True if currently charging | bool
easee2MQTT/{charger_ID}/smartcharging_enabled | Whether smart-charging is enabled | bool
easee2MQTT/{charger_ID}/latest_pulse | Last pulse from charger | Datetime (%Y-%m-%d %H:%M:%S)
easee2MQTT/{charger_ID}/charging_current | Maximum dynamic charging current | Ampere

### Subscribed topics
You can publish to these topics to control your charger. 

Topic | Payload | Description
--- | --- | ---
easee2MQTT/{charger_ID}/cable_lock/set | {true} or {false} | Locks or unlocks cable in charger*
easee2MQTT/{charger_ID}/charging_enabled/set | {true} or {false} | Enables or diables charger
easee2MQTT/{charger_ID}/smartcharging_enabled/set | {true} or {false} | Enables or diables smartcharging
easee2MQTT/{charger_ID}/charging_current/set | INT | Sets maximum charging current
easee2MQTT/{charger_ID}/ping | {true} | Force script to publish ahead of schedule

\* This will only work when the cable is not in a car.