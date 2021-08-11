import requests
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--username", help="""Enter valid username 
                    e-mail or phone number including country code, 
                    i.e +47xxxxxxxx""")
parser.add_argument("--password", help="""Enter valid password
                    for your Easee account""")
args = parser.parse_args()


from requests.api import request

url = "https://api.easee.cloud/api/accounts/token"

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json-patch+json"
}

body = {
    "userName": args.username,
    "password": args.password
}

response = requests.request("POST", url, headers=headers, json=body)

json_obj = json.loads(response.text)
print(json_obj['accessToken'])
auth = "Bearer " + json_obj['accessToken']

chargers_url = "https://api.easee.cloud/api/accounts/chargers"
chargers_headers = {
    "Accept": "application/json",
    "Authorization": auth }


resp2 = requests.request("GET", url = chargers_url, headers = chargers_headers)

print(resp2.text)
