import os
import json
import requests
from os import listdir
from dotenv import load_dotenv


while True:
    folder_path = 'translog'
    list_files = listdir(folder_path)

    try:
        for file_name in list_files:
            print(file_name)

            if file_name.endswith(".json"):
                try:
                    with open(os.path.join(folder_path, file_name), 'r') as file:
                        data = json.load(file)

                    ticketCode = data.get("ticket_code", "")
                    translog = data.get("translog")
                    plate = data.get("plate")
                    card_data = data.get("card_data")
                    end_time = data.get("end_time")
                    transaction = data.get("transaction", {})

                    print(ticketCode)
                    print(translog)
                    print(plate)
                    print(card_data)
                    print(end_time)

                    try:
                        # load_dotenv("/home/pi/parking-out/.env")

                        server = "http://192.168.99.10/api"
                        url = server + "/update-translog"
                        headers = {'Content-Type': 'application/json'}

                        safe_card_data = card_data or {}

                        response = requests.post(url, json={
                            "ticket_code": transaction.get("ticket_code"),
                            "total_time": transaction.get("total_time"),
                            "total_price": transaction.get("total_price"),
                            "translog": translog,
                            "emoney_card_number": card_data.get("card_number", ""),
                            "emoney_card_type": card_data.get("card_type", ""),
                            "mid": card_data.get("merchant_id", ""),
                            "tid": card_data.get("terminal_id", ""),
                            "plat_out": plate,
                            "end_time": end_time
                        },
                            headers=headers,
                            timeout=10)

                        if response.status_code == 200:
                            data = response.json()
                            print(json.dumps(data))
                            print("Success update translog")

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
