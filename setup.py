from tabulate import tabulate
from getpass import getpass
import paho.mqtt.client as mqtt
import time
import json
import logging
from logging.handlers import RotatingFileHandler
from easee2mqtt import get_access_token
import requests

logfile = "easeelog.log"

logging.basicConfig(handlers=[RotatingFileHandler(logfile, 
                    maxBytes=500000, backupCount=0)], 
level=logging.INFO,
format="[%(asctime)s] %(levelname)s %(message)s",
datefmt='%Y-%m-%d %H:%M:%S')

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Successfully connected to MQTT-broker")
        logging.info("Successfully connected to MQTT-broker")
    elif rc == 1:
        print("connection refused, unacceptable protocol version")
        logging.warning("connection refused, unacceptable protocol version")
    elif rc == 2:
        print("Connection refused, identifier rejected")
        logging.warning("Connection refused, identifier rejected")
    elif rc == 3:
        print("Connection refused, server unavailable")
        logging.warning("Connection refused, server unavailable")
    elif rc == 4:
        print("Connection refused, bad user name or password")
        logging.warning("Connection refused, bad user name or password")
    elif rc == 5:
    	print("Connection refused, not authorized")
    	logging.warning("Connection refused, not authorized")


def get_chargers():
    chargers_url = "https://api.easee.cloud/api/accounts/chargers"
    chargers_headers = {
        "Accept": "application/json",
        "Authorization": "Bearer " + settings['access_token']}

    resp = requests.request("GET", url = chargers_url, headers = chargers_headers)
    parsed = resp.json()

    if resp.status_code == 200:
        logging.info("Recieved chargers from Easee")
    else:
        logging.warning("Failed to fetch chargers. Response code: "
                        f"{resp.status_code}")
        return False

    chargers = []
    for circuit in parsed[0].get("circuits", []):
        for charger in circuit.get("chargers", []):
            chargers.append(charger['id'])

    logging.info(f"Chargers identified: {chargers}")

    return chargers

easee_connection = False
mqtt_connection = False
settings = {}

if __name__ == "__main__":
    logging.info("Starting setup.")
    print("Running setup of Easee2MQTT.")
    print()

    while easee_connection is False:
        easee_username = input("Please input e-mail of Easee account: ")
        easee_password = getpass("Please input password of Easee account: ")
        access_token, expiry = get_access_token(easee_username, easee_password)
        if access_token:
            settings['access_token'] = access_token
            settings['expiry'] = expiry
            settings['easee_username'] = easee_username
            settings['easee_password'] = easee_password
            print("Successfully connected to Easee!")

            chargers = get_chargers()
            print("The following chargers has been found on this account. "
                  "Note that the charger ID shown here will make up the MQTT-topic.")
            print("If you get a new charger, please re-run settings.")
            settings['chargers'] = chargers
            for charger in chargers:
                print(charger)
            easee_connection = True
    
    while mqtt_connection is False:
        mqtt_adress = input("Please input IP or adress of MQTT-broker: ")
        mqtt_port = input("Input MQTT-port, default=1883: ")
        if mqtt_port == '':
            mqtt_port = 1883
        mqtt_username = input("Input MQTT-username, leave blank if no authentication is required: ")
        if mqtt_username != '':
            mqtt_password = getpass("Input MQTT-password: ")

        client = mqtt.Client("Easee2MQTT")
        if mqtt_username != '':
            client.username_pw_set(username=mqtt_username, password=mqtt_password)
        client.on_connect = on_connect
        client.loop_start()
        print("Please wait, testing connection...")

        try:
            client.connect(mqtt_adress, port=mqtt_port)
            time.sleep(5)
            client.loop_stop()
            if mqtt_username != '':
                settings['mqtt_username'] = mqtt_username
                settings['mqtt_password'] = mqtt_password
            mqtt_connection = True
        except:
            client.loop_stop()
            print("Couldn't connect to the broker, please check settings.")
            logging.warning("Failed to connect to MQTT-broker")       

    print("Available QOS-levels of MQTT: ")
    print("0 - At most once")
    print("1 - At least once")
    print("2 - Exactly once")

    mqtt_qos = input("Input QOS-level, recommended 1: ")
    if mqtt_qos == '':
        mqtt_qos = 1
    settings['mqtt_adress'] = mqtt_adress
    settings['mqtt_port'] = mqtt_port
    settings['mqtt_qos'] = mqtt_qos
    settings['debuglevel'] = "info"

    print()
    print("Setup complete. The program can now be started.")
    logging.info("Setup complete. The program can now be started.")
    print()

    with open('settings.json', 'w') as fp:
        json.dump(settings, fp, indent=4, sort_keys=True)
            