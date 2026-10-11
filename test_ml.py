import urllib.request
import json

data = json.dumps({"age": 25, "sys_bp": 115, "dia_bp": 75, "bs": 90, "temp": 36, "hr": 75}).encode('utf-8')
req = urllib.request.Request("http://127.0.0.1:5000/predict", data=data, headers={'Content-Type': 'application/json'})
try:
    response = urllib.request.urlopen(req)
    print("Response:", response.read().decode())
except Exception as e:
    print("Error:", e)
