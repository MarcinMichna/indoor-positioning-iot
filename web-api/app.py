from flask import Flask, request
import logging
from threading import Lock
import json
import copy
from datetime import datetime

espCount = 4
excludeThreshold = 2
lengthThreshold = 1000
numberOfHotspotSignals = 5000
maxRssiDiff = 5  # in db
maxDeviceSignalAge = 40  # in sec
maxHotspotAge = 20  # in sec

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

lock = Lock()

dataWifi = []
dataBle = []

recentDataWifi = []
recentDataBt = []
hotspotData = []

watchedDevicesWifi = []
watchedDevicesBt = []

espDataWifi = {}
espDataBt = {}
avgEspDataWifi = {}
avgEspDataBt = {}

avgDeviceDataBt = {}
avgDeviceDataWifi = {}

hotspotName = ""
referenceSignalsWifi = {}
referenceSignalsBt = {}


@app.route('/hotspotName', methods=['POST'])
def updateHotspotName():
    with lock:
        global hotspotName
        hotspotName = request.json["name"]
        hotspotData.clear()
        app.logger.info("Updated hotspot name: {}".format(hotspotName))
        return json.dumps({"status": "OK"}, default=str)


@app.route('/hotspot', methods=['GET'])
def getHotspot():
    with lock:
        timestamp = datetime.now().replace(microsecond=0)
        recent = list(filter(lambda x: (timestamp - x["timestamp"]).seconds < maxHotspotAge, hotspotData))
        app.logger.info("Hotspot data size: {}".format(len(recent)))
        return json.dumps({"data": recent}, default=str)


@app.route('/hotspotClear', methods=['GET'])
def clearHotspot():
    with lock:
        hotspotData.clear()
        return json.dumps({"status": "OK"}, default=str)


@app.route('/hotspotArea', methods=['GET'])
def getHotspotArea():
    with lock:
        return json.dumps({"data": hotspotData}, default=str)


@app.route('/hotspotAge', methods=['POST'])
def setHotspotMaxAge():
    with lock:
        global maxHotspotAge
        maxHotspotAge = int(request.json["age"])
    return json.dumps({"status": "OK"}, default=str)


@app.route('/watchedDevices', methods=['POST'])
def updateWatchedDevices():
    with lock:
        global referenceSignalsWifi
        global referenceSignalsBt

        devicesWifi = request.json["wifi"]
        devicesBt = request.json["bt"]
        watchedDevicesWifi.clear()
        watchedDevicesWifi.extend(devicesWifi)

        watchedDevicesBt.clear()
        watchedDevicesBt.extend(devicesBt)

        referenceSignalsWifi = copy.deepcopy(avgDeviceDataWifi)
        referenceSignalsBt = copy.deepcopy(avgDeviceDataBt)

        app.logger.info("Updated list watched devices wifi: {}, bt: {}".format(devicesWifi, devicesBt))
        return json.dumps({"status": "OK"}, default=str)


@app.route('/excludedDevices', methods=['GET'])
def getExcludedDevices():
    with lock:
        notMatchingWifiNumber = {}
        notMatchingBtNumber = {}

        calcMatchesWifi(notMatchingWifiNumber)
        calcMatchesBle(notMatchingBtNumber)

        notMatchingWifi = []
        notMatchingBt = []

        for device, value in notMatchingWifiNumber.items():
            if value >= excludeThreshold:
                notMatchingWifi.append(device)

        for device, value in notMatchingBtNumber.items():
            if value >= excludeThreshold:
                notMatchingBt.append(device)

        return json.dumps({"wifi": notMatchingWifi, "bt": notMatchingBt}, default=str)


def calcMatchesBle(notMatchingBtNumber):
    for device in watchedDevicesBt:
        if device in avgDeviceDataBt:
            for name, rssi in avgDeviceDataBt[device].items():
                if device in referenceSignalsBt:
                    if name in referenceSignalsBt[device]:
                        if abs(referenceSignalsBt[device][name] - avgDeviceDataBt[device][name]) > maxRssiDiff:
                            if name not in notMatchingBtNumber:
                                notMatchingBtNumber[name] = 1
                            else:
                                notMatchingBtNumber[name] += 1


def calcMatchesWifi(notMatchingWifiNumber):
    for device in watchedDevicesWifi:
        if device in avgDeviceDataWifi:
            for ssid, rssi in avgDeviceDataWifi[device].items():
                if device in referenceSignalsWifi:
                    if ssid in referenceSignalsWifi[device]:
                        if abs(referenceSignalsWifi[device][ssid] - avgDeviceDataWifi[device][ssid]) > maxRssiDiff:
                            if device not in notMatchingWifiNumber:
                                notMatchingWifiNumber[device] = 1
                            else:
                                notMatchingWifiNumber[device] += 1


@app.route('/add', methods=['POST'])
def add():
    with lock:
        timestamp = datetime.now().replace(microsecond=0)
        wifiJson = request.json["wifi"]
        bleJson = request.json["ble"]

        updateWifiResults(wifiJson, timestamp)
        updateBleResults(bleJson, timestamp)
        filterRecentResults(timestamp)
        clearEspData()
        processWifiData()
        processBleData()
        calcAvgEspData()
        structureData()

        return json.dumps({"status": "OK"}, default=str)


def structureData():
    for key, value in avgEspDataWifi.items():
        for ssid, rssi in value.items():
            if ssid not in avgDeviceDataWifi:
                avgDeviceDataWifi[ssid] = {}
            avgDeviceDataWifi[ssid][key] = rssi
    for key, value in avgEspDataBt.items():
        for name, rssi in value.items():
            if name not in avgDeviceDataBt:
                avgDeviceDataBt[name] = {}
            avgDeviceDataBt[name][key] = rssi


def processBleData():
    global espDataBt
    for i in recentDataBt:
        for k in range(1, 6):
            espName = "ESP_" + str(k)
            espBtName = espName + "_BT"
            if i["esp"] == espName:
                if i["name"] in espDataBt[espBtName]:
                    espDataBt[espBtName][i["name"]].append(i)
                elif i["name"] != "":
                    espDataBt[espBtName][i["name"]] = [i]
                else:
                    espDataBt[espBtName][i["addr"]] = [i]


def processWifiData():
    global espDataWifi
    for i in recentDataWifi:
        for k in range(1, 5):
            espName = "ESP_" + str(k)
            espWifiName = espName + "_WIFI"
            if i["esp"] == espName:
                if i["ssid"] in espDataWifi[espWifiName]:
                    espDataWifi[espWifiName][i["ssid"]].append(i)
                else:
                    espDataWifi[espWifiName][i["ssid"]] = [i]


def filterRecentResults(timestamp):
    global recentDataWifi
    recentDataWifi = list(filter(lambda x: (timestamp - x["timestamp"]).seconds < maxDeviceSignalAge, dataWifi))
    global recentDataBt
    recentDataBt = list(filter(lambda x: (timestamp - x["timestamp"]).seconds < maxDeviceSignalAge, dataBle))


def updateBleResults(bleJson, timestamp):
    for i in bleJson:
        if len(dataWifi) > lengthThreshold:
            dataBle.pop(0)
        i["timestamp"] = timestamp
        dataBle.append(i)


def updateWifiResults(wifiJson, timestamp):
    for i in wifiJson:
        if len(dataWifi) > lengthThreshold:
            dataWifi.pop(0)

        i["timestamp"] = timestamp
        dataWifi.append(i)

        if len(hotspotData) > numberOfHotspotSignals:
            hotspotData.pop(0)
        if i["ssid"] == hotspotName:
            hotspotData.append(i)


def calcAvgEspData():
    global avgEspDataWifi
    global avgEspDataBt
    clearAvgEspData()

    for espKey, value in espDataWifi.items():
        for areaKey, areaItem in value.items():
            rssiList = []
            for item in areaItem:
                rssiList.append(item["rssi"])
            if len(rssiList) > 0:
                avgEspDataWifi[espKey][areaKey] = sum(rssiList) / len(rssiList)

    for espKey, value in espDataBt.items():
        for areaKey, areaItem in value.items():
            rssiList = []
            for item in areaItem:
                rssiList.append(item["rssi"])
            if len(rssiList) > 0:
                avgEspDataBt[espKey][areaKey] = sum(rssiList) / len(rssiList)


def clearEspData():
    global espDataWifi
    global espDataBt

    espDataWifi = {
        "ESP_1_WIFI": {},
        "ESP_2_WIFI": {},
        "ESP_3_WIFI": {},
        "ESP_4_WIFI": {}
    }

    espDataBt = {
        "ESP_1_BT": {},
        "ESP_2_BT": {},
        "ESP_3_BT": {},
        "ESP_4_BT": {}
    }


def clearAvgEspData():
    global avgEspDataWifi
    global avgEspDataBt
    for i in range(1, espCount + 1):
        nameWifi = "ESP_" + str(i) + "_WIFI"
        nameBT = "ESP_" + str(i) + "_BT"
        avgEspDataWifi[nameWifi] = {}
        avgEspDataBt[nameBT] = {}


def setupVariables():
    global espDataWifi
    global espDataBt
    global avgEspDataWifi
    global avgEspDataBt

    for i in range(1, espCount + 1):
        nameWifi = "ESP_" + str(i) + "_WIFI"
        nameBT = "ESP_" + str(i) + "_BT"
        espDataWifi[nameWifi] = {}
        espDataBt[nameBT] = {}
        avgEspDataWifi[nameWifi] = {}
        avgEspDataBt[nameBT] = {}


#################
##### DEBUG #####
#################

@app.route('/')
def hello_world():
    app.logger.info("root path request - OK")
    timestamp = datetime.now().replace(microsecond=0)
    return json.dumps({"timestamp": timestamp}, default=str)


@app.route('/checkGet', methods=['GET'])
def checkGet():
    # app.logger.info(dataWifi)
    # app.logger.info(dataBle)
    return json.dumps({"wifi": dataWifi, "ble": dataBle, "time": datetime.now().replace(microsecond=0)}, default=str)


@app.route('/checkRecentData', methods=['GET'])
def checkRecentData():
    return json.dumps({"wifi": recentDataWifi, "bt": recentDataBt}, default=str)


@app.route('/checkHotspotData', methods=['GET'])
def checkHotspotData():
    return json.dumps({"hotspot": hotspotData}, default=str)


@app.route('/checkEspData', methods=['GET'])
def checkEspData():
    return json.dumps({"wifi": espDataWifi, "bt": espDataBt}, default=str)


@app.route('/checkAvgData', methods=['GET'])
def checkAvgData():
    return json.dumps({"wifi": avgEspDataWifi, "bt": avgEspDataBt}, default=str)


@app.route('/checkAvgDeviceData', methods=['GET'])
def checkAvgDeviceData():
    return json.dumps({"wifi": avgDeviceDataWifi, "bt": avgDeviceDataBt}, default=str)


@app.route('/checkReferenceData', methods=['GET'])
def checkReferenceData():
    return json.dumps({"wifi": referenceSignalsWifi}, default=str)


if __name__ == '__main__':
    setupVariables()
    app.run(host='0.0.0.0', debug=True)
