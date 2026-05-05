import os
import json
import requests
from os import listdir
from dotenv import load_dotenv


while True:
    folder_path = 'parking-out/logs-reader'
    list_files = listdir(folder_path)

    try:
        for file_name in list_files:
            print(file_name)

            if file_name.endswith(".json"):
                try:
                    with open(os.path.join(folder_path, file_name), 'r') as file:
                        data = json.load(file)

                    ticket_code = data.get("ticket_code", "")
                    translog = data.get("translog")

                    print(ticket_code)
                    print(translog)

                    try:
                        load_dotenv("/home/pi/parking-out/.env")

                        server = os.getenv('SERVER')
                        url = server + "/store-translog"
                        headers = {'Content-Type': 'application/json'}

                        response = requests.post(url, json={
                            "ticket_code": ticket_code,
                            "translog": translog,
                        },
                            headers=headers,
                            timeout=10)

                        if response.status_code == 200:
                            data = response.json()
                            print(json.dumps(data))
                            print("Success store translog")

                            os.remove(os.path.join(folder_path, file_name))
                            print("Success remove file")
                        else:
                            data = response.json()
                            print(json.dumps(data))

                            if data.get("message") == "Transaction not found":
                                os.remove(os.path.join(folder_path, file_name))
                                print("Success remove file")
                    except Exception as e:
                        print(e)
                        print("Error connect to server")
                except Exception as e:
                    print(e)
                    print("Error connect to server")
    except Exception as e:
        print(e)
        print("Error connect to server")
