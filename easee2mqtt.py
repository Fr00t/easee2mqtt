#!/usr/bin/python3
import requests
import json
import time
import sys
import datetime
import logging
from logging.handlers import RotatingFileHandler
import paho.mqtt.client as mqtt
from requests.api import request
import os
import threading
from datetime import datetime, timezone

logfile = "easeelog.log"

logging.basicConfig(handlers=[RotatingFileHandler(logfile, 
                    maxBytes=500000, 
                    backupCount=0)], 
                    level=logging.INFO,
                    format="[%(asctime)s] %(levelname)s %(message)s",
                    datefmt='%Y-%m-%d %H:%M:%S')

settings = {}

def get_access_token(username,password):
    url = "https://api.easee.cloud/api/accounts/token"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json-patch+json"
    }

    body = {
        "userName": username,
        "password": password
    }

    response = requests.request("POST", url, headers=headers, json=body)
    logging.debug(f"Response from get_access_log: {response}")
    if response.status_code == 200:
        logging.info("Successfully connected to Easee")
    else:
        logging.warning("Failed to connect to Easee. Response code: "
                        f"{response.status_code}")
        return False
    json_obj = json.loads(response.text)
    expiry = time.time() + json_obj['expiresIn']
    return json_obj['accessToken'], expiry


def response_codes(code):
    if code == 200 or code == 202:
        return "Command successfully sent to charger"
    elif code == 400:
        return "Command has missing/invalid values"
    elif code == 401:
        return "Missing authorization data. Check 'Authorization' header"
    elif code == 403:
        return "Forbidden. Authorization set, but access to resource is denied"
    elif code == 415:
        return "Payload format is in an unsupported format"
    elif code == 500:
        return "Oops! Unexpected internal error. Request has been logged and code monkeys warned"
    elif code == 503:
        return "Server gateway cannot reach API. Try again in about a minute..."
    elif code == 504:
        return "Unable to deliver commands upstream. End device is not reachable, or a problem with queueing the device command"
    else:
        return f"Unknown response code: {code}"


def get_latest_session(charger_id):
    details_url = f"https://api.easee.cloud/api/chargers/{charger_id}/sessions/latest"
    
    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer " + settings['access_token']}

    resp = requests.request("GET", url = details_url, headers = headers)
    parsed = resp.json()
    if resp.status_code != 200:
        logging.warning(f"Response code {resp.status_code} when trying to get_latest_session")
    return parsed


def check_expiration():
    global settings
    if settings['expiry'] - time.time() < 350:
        logging.info("Token expires in less than 350 seconds. Fetching a new token.")
        access_token, expiry = get_access_token(settings['easee_username'], settings['easee_password'])
        settings['access_token'] = access_token
        settings['expiry'] = expiry
        with open('settings.json', 'w') as fp:
            json.dump(settings, fp, indent=4, sort_keys=True)
        logging.info("Successfully retrieved and stored a new token.")
    else:
        logging.info("Token is not up for refresh.")


def get_state(charger_id):
    url = f"https://api.easee.cloud/api/chargers/{charger_id}/state"
    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer " + settings['access_token']}
    resp = requests.request("GET", url = url, headers=headers)
    parsed = resp.json()
    if resp.status_code != 200:
        logging.warning(f"Response code {resp.status_code} when trying to get_state")
    return parsed


def publish_state(charger):
    state = get_state(charger)
    config = get_config(charger)
    latest_session = get_latest_session(charger)
    latest_pulse = datetime.strptime(state['latestPulse'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(tz=None).strftime("%Y-%m-%d %H:%M:%S")
    logging.debug(f"Publish_state - Latest pulse: {latest_pulse}")
    if state['totalPower'] > 0:
        charging_state = "True"
    else:
        charging_state = "False"

    client.publish(f"easee2MQTT/{charger}/energy_consumption", round(state['lifetimeEnergy'],2))
    client.publish(f"easee2MQTT/{charger}/current_session", round(state['sessionEnergy'],2))
    client.publish(f"easee2MQTT/{charger}/previous_session", round(latest_session['sessionEnergy'],2))
    client.publish(f"easee2MQTT/{charger}/voltage", round(state['voltage'],1))
    client.publish(f"easee2MQTT/{charger}/power", round(state['totalPower'],2))
    client.publish(f"easee2MQTT/{charger}/cable_lock", state['cableLocked'])
    client.publish(f"easee2MQTT/{charger}/charging_enabled", config['isEnabled'])
    client.publish(f"easee2MQTT/{charger}/charging", charging_state)
    client.publish(f"easee2MQTT/{charger}/smartcharging_enabled", state['smartCharging'])
    client.publish(f"easee2MQTT/{charger}/latest_pulse", latest_pulse)
    client.publish(f"easee2MQTT/{charger}/charging_current", state['dynamicChargerCurrent'])


def on_message(client, userdata, message):
    logging.info(f"Message received on topic: {message.topic}, payload: {str(message.payload.decode('utf-8'))}")
    charger = message.topic.split("/")[1]
    headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + settings['access_token']}

    if message.topic.split("/")[2] == "cable_lock":
        url = "https://api.easee.cloud/api/chargers/"+charger+"/commands/lock_state"
        data = {
            "state": str(message.payload.decode("utf-8"))
        }
        resp = requests.post(url, headers= headers, json = data)
        callback_topic = f"easee2MQTT/{charger}/cable_lock"
        
    elif message.topic.split("/")[2] == "charging_enabled":
        url = "https://api.easee.cloud/api/chargers/"+charger+"/settings"
        if (str(message.payload.decode("utf-8")).casefold() == "true" or 
            str(message.payload.decode("utf-8")).casefold() == "false"):
            data = {
                'enabled' : str(message.payload.decode("utf-8")).title()
            }
            resp = requests.post(url, headers=headers, json = data)
            callback_topic = f"easee2MQTT/{charger}/charging_enabled"
            
        else:
            logging.warning("Couldn't identify payload. 'true' or 'false' is only supported values.")
        
    
    elif message.topic.split("/")[2] == "ping":
        logging.info("Running publish_state from a manual ping")
        publish_state(charger)

    elif message.topic.split("/")[2] == "smartcharging_enabled":
        if (str(message.payload.decode("utf-8")).casefold() == "true" or 
            str(message.payload.decode("utf-8")).casefold() == "false"):
            url = "https://api.easee.cloud/api/chargers/"+charger+"/settings"
            data = {
                "smartCharging" : message.payload.decode("utf-8").title()
            }
            resp = requests.post(url, headers=headers, json = data)
            callback_topic = f"easee2MQTT/{charger}/smartcharging_enabled"
            
    elif message.topic.split("/")[2] == "charging_current":
        if float(message.payload.decode('utf-8')) < 33.0:
            url = "https://api.easee.cloud/api/chargers/"+charger+"/settings"
            data = {
                "dynamicChargerCurrent" : message.payload.decode('utf-8')
            }
            resp = requests.post(url, headers=headers, json = data)
            callback_topic = f"easee2MQTT/{charger}/charging_current"
        else:
            logging.warning(f"Couldn't publish new charging_current")
   
    try:
        logging.info(f"Manually publishing setting {message.topic.split('/')[2]} for {charger}")
        client.publish(callback_topic, message.payload.decode('utf-8'))        
        t = threading.Timer(5.0, publish_state, [charger])
        t2 = threading.Timer(15.0, publish_state, [charger])
        t.start()
        t2.start()
    
    except:
        logging.warning(f"Couldn't publish manually for message: {message}")
   
    try:
        #Log a warning if we still have a status_code
        if resp.status_code == 200 or resp.status_code ==202:
            logging.info(f"Response {response_codes(resp.status_code)} - Payload: {message.payload.decode('utf-8')}")
        else:
            logging.warning(f"Failed to send command to charger. Response code {resp.status_code} - {response_codes(resp.status_code)}")
    except:
        logging.warning(f"No status_code from recieved message: {message}")


def get_config(charger):
    url = "https://api.easee.cloud/api/chargers/"+charger+"/config"
    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer " + settings['access_token']}
    resp = requests.request("GET", url = url, headers=headers)
    parsed = resp.json()
    if resp.status_code != 200:
        logging.warning(f"Response code {resp.status_code} when trying to get_latest_session")
    return parsed

if __name__ == "__main__":
    logging.info("Script is starting. Looking for settings")
    try:
        settingspath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
        with open(settingspath) as json_file:
            settings = json.load(json_file)
        logging.info("Successfully opened settings.")
    except FileNotFoundError:
        logging.warning(f"Couldn't find settings. Run setup.py and make sure you are in the right folder")
        sys.exit()
    
    check_expiration()

    client = mqtt.Client("Easee2MQTT")
    if "mqtt_password" in settings:
        client.username_pw_set(username=settings['mqtt_username'], password=settings['mqtt_password']) 
    client.connect(settings['mqtt_adress'], port=settings['mqtt_port'])
    client.loop_start()

    for charger in settings['chargers']:
        logging.info(f"Subscribing to topics for charger {charger}.")
        client.subscribe("easee2MQTT/"+charger+"/cable_lock/set")
        client.subscribe("easee2MQTT/"+charger+"/charging_enabled/set")
        client.subscribe("easee2MQTT/"+charger+"/ping")
        client.subscribe("easee2MQTT/"+charger+"/smartcharging_enabled/set")
        client.subscribe("easee2MQTT/"+charger+"/charging_current/set")
    client.on_message = on_message
    

    try:
        while True:
            try:
                check_expiration()
            except:
                logging.warning("Failed to check expiration. Retrying in 5 minutes")

            for charger in settings['chargers']:
                try:
                    logging.debug(f"Fetching and publishing latest stats of {charger}")
                    publish_state(charger)
                except:
                    logging.warning(f"Failed to fetch and publish new stats of {charger}. Will retry in 5 minutes.")

            time.sleep(300)

    except KeyboardInterrupt:
        print("Exiting program")
        client.loop_stop()