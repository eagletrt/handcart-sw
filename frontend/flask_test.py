import datetime
import pytz
import random

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.config["DEBUG"] = True

tz = pytz.timezone('Europe/Rome')


# =PAGES=========================================================================

@app.route('/', methods=['GET'])
def home():
    return render_template("index.html")


@app.route('/warning')
def warning():
    return render_template("warning.html")


@app.route('/error')
def error():
    return render_template("error.html")


@app.route('/settings')
def settings():
    return render_template("settings.html")


@app.route('/charts')
def charts():
    chart = request.args.get("chart")

    return render_template("charts.html", c=chart)


# =UTILITIES=====================================================================

def getLastNSeconds(n):
    now = datetime.datetime.now(tz)
    a = [(now - datetime.timedelta(seconds=i)) for i in range(n)]
    a.reverse()  # an array with the last n seconds form the older date to the now date

    return a


# =GETS==========================================================================

# -HANDCART-(backend)------------------------------------------------------------

@app.route('/handcart/status', methods=['GET'])
def get_hc_status():
    data = {
        "timestamp": "2020-12-01:ora",
        "status": "STATE.IDLE",
        "entered": "2020-12-01:ora"
    }

    resp = jsonify(data)
    resp.status_code = 200
    return resp


# -END-HANDCART-(backend)--------------------------------------------------------
# -BMS-HV------------------------------------------------------------------------

@app.route('/bms-hv/status', methods=['GET'])
def get_bms_status():
    data = {
        "timestamp": "2020-12-01:ora",
        "status": "STATE.TS_ON"  # TS_OFF, PRECHARGE, TS_ON, FATAL
    }

    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/warnings', methods=['GET'])
def get_bms_warnings():
    data = {
        "timestamp": "2020-12-01:ora",
        "warnings": [{
            "id": "0",
            "desc": "Sto esplodendo"
        },
            {
                "id": "5",
                "desc": "cell 5 overvoltage"
            }]
    }

    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/errors', methods=['GET'])
def get_bms_errors():
    data = {
        "timestamp": "2020-12-01:ora",
        "errors": [{
            "desc": "Sto esplodendo"
        },
            {
                "desc": "cell 5 overvoltage"
            }]
    }

    resp = jsonify(data)
    resp.status_code = 200
    return resp


# -BMS-CELLS-DATA
@app.route('/bms-hv/cells', methods=['GET'])
def get_bms_cells():
    data = {
        "timestamp": "2020-12-01:ora",
        "data": []
    }

    ncells = 108
    digits = 3
    min = 0
    max = 100
    n = 30

    last_n_seconds = getLastNSeconds(n)

    for timestamp in last_n_seconds:
        element = {
            "timestamp": timestamp,
            "cells": []
        }
        for i in range(1, ncells + 1):
            value = round(random.uniform(min, max), digits)
            cell = {
                "id": i,
                "voltage": value
            }
            element["cells"].append(cell)
        data["data"].append(element)

    c = request.args.get("cell")
    # get all data, if there's a parameter in the request, then it will return
    # a json with only the specified cell values
    if c != None and c != "":
        filtered = {
            "timestamp": "2020-12-01:ora",
            "data": []
        }

        for i in data["data"]:
            for j in i["cells"]:
                if j["id"] == int(c):
                    element = {
                        "timestamp": i["timestamp"],
                        "voltage": j["voltage"]
                    }

                    filtered["data"].append(element)
                    break  # no need to cycle over the whole array

        resp = jsonify(filtered)
    else:
        resp = jsonify(data)

    resp.status_code = 200
    return resp


@app.route('/bms-hv/cells/last', methods=['GET'])
def get_last_bms_cells():
    timestamp = datetime.datetime.now(tz)
    data = {
        "timestamp": timestamp,
        "cells": []
    }

    ncells = 108
    digits = 3
    min = 0
    max = 100

    for i in range(1, ncells + 1):
        value = round(random.uniform(min, max), digits)
        cell = {
            "id": i,
            "voltage": value
        }
        data["cells"].append(cell)

    c = request.args.get("cell")
    # get all data, if there's a parameter in the request, then it will return
    # a json with only the specified cell values
    if c != None and c != "":
        filtered = {}
        for i in data["cells"]:
            if i["id"] == int(c):
                filtered = {
                    "timestamp": timestamp,
                    "voltage": i["voltage"]
                }

                break  # no need to cycle over the whole array

        resp = jsonify(filtered)
    else:
        resp = jsonify(data)

    resp.status_code = 200
    return resp


# -BMS-VOLTAGE-DATA
@app.route('/bms-hv/volt', methods=['GET'])
def get_bms_volt():
    data = {
        "timestamp": "2020-12-01:ora",
        "data": []
    }

    n = 100
    min = 0
    max = 100

    last_100_seconds = getLastNSeconds(n)

    for timestamp in last_100_seconds:
        value = random.randrange(min, max)

        voltage = {
            "timestamp": timestamp,
            "volts": value
        }
        data["data"].append(voltage)

    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/volt/last', methods=['GET'])
def get_last_bms_volt():
    min = 0
    max = 100
    value = random.randrange(min, max)
    timestamp = datetime.datetime.now(tz)

    data = {
        "timestamp": timestamp,
        "volts": value
    }

    resp = jsonify(data)
    resp.status_code = 200
    return resp


# -BMS-AMPERE-DATA
@app.route('/bms-hv/ampere', methods=['GET'])
def get_bms_ampere():
    data = {
        "timestamp": "2020-12-01:ora",
        "data": []
    }

    n = 100
    min = 0
    max = 10

    last_100_seconds = getLastNSeconds(n)

    for timestamp in last_100_seconds:
        value = random.randrange(min, max)

        amperes = {
            "timestamp": timestamp,
            "amperes": value
        }
        data["data"].append(amperes)

    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/ampere/last', methods=['GET'])
def get_last_bms_ampere():
    min = 0
    max = 10
    value = random.randrange(min, max)
    timestamp = datetime.datetime.now(tz)

    data = {
        "timestamp": timestamp,
        "amperes": value
    }

    resp = jsonify(data)
    resp.status_code = 200
    return resp


# -BMS-TEMPERATURE-DATA
@app.route('/bms-hv/temp', methods=['GET'])
def get_bms_temp():
    data = {
        "timestamp": "2020-12-01:ora",
        "data": []
    }

    n = 100
    min = 0
    max = 10

    last_100_seconds = getLastNSeconds(n)

    for timestamp in last_100_seconds:
        value = random.randrange(min, max)

        temperature = {
            "timestamp": timestamp,
            "temp": value
        }
        data["data"].append(temperature)

    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/temp/last', methods=['GET'])
def get_last_bms_temp():
    min = 0
    max = 10
    value = random.randrange(min, max)
    timestamp = datetime.datetime.now(tz)

    data = {
        "timestamp": timestamp,
        "temp": value
    }

    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/heat', methods=['GET'])
def get_bms_heat():
    min = 20
    max = 250
    ncells = 108

    timestamp = datetime.datetime.now(tz)

    data = {
        "timestamp": timestamp,
        "data": []
    }

    for i in range(1, ncells + 1):
        value = random.randrange(min, max)
        element = {
            "cell": i,
            "temp": value
        }
        data["data"].append(element)

    resp = jsonify(data)
    resp.status_code = 200
    return resp


# -END-BMS-HV--------------------------------------------------------------------
# -BRUSA-------------------------------------------------------------------------

@app.route('/brusa/status', methods=['GET'])  # 8-23 WARNINGS
def get_brusa_status():
    data = {
        "timestamp": "2020-12-01:ora",
        "status": [{
            "desc": "brusa on bla bla",
            "pos": 0
        },
            {
                "desc": "brusa current limited",
                "pos": 2
            }]
    }

    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/brusa/errors', methods=['GET'])
def get_brusa_errors():
    data = {
        "timestamp": "2020-12-01:ora",
        "errors": [{
            "desc": "brusa is on fire",
            "pos": 3
        },
            {
                "desc": "brusa current limited",
                "pos": 5
            }]
    }

    resp = jsonify(data)
    resp.status_code = 200
    return resp


# -END-BRUSA---------------------------------------------------------------------
# =COMMANDS======================================================================

@app.route('/command/setting', methods=['POST'])
def recv_command():
    comType = request.form.get("comType")
    value = request.form.get("value")

    command = {
        "com-type": comType,
        "value": value
    }

    # print(command["com-type"], " - ", command["value"])
    command = jsonify(command)

    return command


@app.route('/command/setting', methods=['GET'])
def get_settings_command():
    data = [{
        "com-type": "cutoff",
        "value": 150
    },
        {
            "com-type": "max-c-o",
            "value": 5
        },
        {
            "com-type": "fast-charge",
            "value": False
        }]

    resp = jsonify(data)
    resp.status_code = 200
    return resp


if __name__ == '__main__':
    app.run()
