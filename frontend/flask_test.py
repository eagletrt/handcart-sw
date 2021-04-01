from flask import Flask, render_template, url_for, request, jsonify
import random, datetime, pytz

app = Flask(__name__)
app.config["DEBUG"] = True

tz = pytz.timezone('Europe/Rome')

#=PAGES=========================================================================

@app.route('/', methods=['GET'])
def home():
    return render_template("index.html")


@app.route('/warning')
def warning():
    return render_template("warning.html")


@app.route('/error')
def error():
    return render_template("error.html")

#=GETS==========================================================================

#-HANDCART-(backend)------------------------------------------------------------

@app.route('/handcart/status/', methods=['GET'])
def get_hc_status():
    data = [{
        "timestamp": "2020-12-01:ora",
        "status": "STATE.IDLE",
        "entered": "2020-12-01:ora"
    }]
    resp = jsonify(data)
    resp.status_code = 200
    return resp

#-END-HANDCART-(backend)--------------------------------------------------------
#-BMS-HV------------------------------------------------------------------------

@app.route('/bms-hv/status/', methods=['GET'])
def get_bms_status():
    data = [{
        "timestamp": "2020-12-01:ora",
        "status": "STATE.TS_ON"         #TS_OFF, PRECHARGE, TS_ON, FATAL
    }]
    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/errors/', methods=['GET'])
def get_bms_errors():
    data = [{
        "timestamp": "2020-12-01:ora",
        "errors": [{
            "code": 1,
            "desc": "Sto esplodendo"
        },
        {
            "code": 2,
            "desc": "cell 5 overvoltage"
        }]
    }]
    resp = jsonify(data)
    resp.status_code = 200
    return resp

#-BMS-CELLS-DATA
@app.route('/bms-hv/cells/', methods=['GET'])
def get_bms_cells():
    data = [{
        "timestamp": "2020-12-01:ora",
        "data": [{
            "timestamp": "2020-12-01:ora",
            "cells": []
        }]
    }]
    ncells = 108
    digits = 3
    min = 0
    max = 100
    for i in range(1, ncells+1):
        value = round(random.uniform(min, max), digits)
        cell = {
            "id": i,
            "voltage": value
        }
        data[0]["data"][0]["cells"].append(cell)

    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/cells/last', methods=['GET'])
def get_last_bms_cells():
    data = [{
        "timestamp": "2020-12-01:ora",
        "cells": []
    }]
    ncells = 108
    digits = 3
    min = 0
    max = 100
    for i in range(1, ncells+1):
        value = round(random.uniform(min, max), digits)
        cell = {
            "id": i,
            "voltage": value
        }
        data[0]["cells"].append(cell)

    resp = jsonify(data)
    resp.status_code = 200
    return resp

#-BMS-VOLTAGE-DATA
@app.route('/bms-hv/volt/', methods=['GET'])
def get_bms_volt():
    data = [{
        "timestamp": "2020-12-01:ora",
        "data": []
    }]

    n = 100
    min = 0
    max = 100

    now = datetime.datetime.now(tz)
    last_100_seconds=[(now - datetime.timedelta(seconds=i)) for i in range(n)]
    last_100_seconds.reverse() # an array with the last n seconds form the older date to the now date

    for timestamp in last_100_seconds:
        value = random.randrange(min, max)

        voltage = {
            "timestamp": timestamp,
            "volts": value
        }
        data[0]["data"].append(voltage)

    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/volt/last', methods=['GET'])
def get_last_bms_volt():
    min = 0
    max = 100
    value = random.randrange(min, max)
    timestamp = datetime.datetime.now(tz)

    data = [{
        "timestamp": timestamp,
        "volts": value
    }]
    
    resp = jsonify(data)
    resp.status_code = 200
    return resp

#-BMS-AMPERE-DATA
@app.route('/bms-hv/ampere/', methods=['GET'])
def get_bms_ampere():
    data = [{
        "timestamp": "2020-12-01:ora",
        "data": []
    }]

    n = 100
    min = 0
    max = 10

    now = datetime.datetime.now(tz)
    last_100_seconds=[(now - datetime.timedelta(seconds=i)) for i in range(n)]
    last_100_seconds.reverse() # an array with the last n seconds form the older date to the now date

    for timestamp in last_100_seconds:
        value = random.randrange(min, max)

        amperes = {
            "timestamp": timestamp,
            "amperes": value
        }
        data[0]["data"].append(amperes)

    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/ampere/last', methods=['GET'])
def get_last_bms_ampere():
    min = 0
    max = 10
    value = random.randrange(min, max)
    timestamp = datetime.datetime.now(tz)

    data = [{
        "timestamp": timestamp,
        "amperes": value
    }]

    resp = jsonify(data)
    resp.status_code = 200
    return resp

#-END-BMS-HV--------------------------------------------------------------------
#-BRUSA-------------------------------------------------------------------------

@app.route('/brusa/status/', methods=['GET']) #8-23 WARNINGS
def get_brusa_status():
    data = [{
        "timestamp": "2020-12-01:ora",
        "status": [{
            "desc": "brusa on bla bla",
            "pos": 0
        },
        {
            "desc": "brusa current limited",
            "pos": 2
        }]
    }]
    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/brusa/errors/', methods=['GET'])
def get_brusa_errors():
    data = [{
        "timestamp": "2020-12-01:ora",
        "errors": [{
            "desc": "brusa is on fire",
            "pos": 3
        },
        {
            "desc": "brusa current limited",
            "pos": 5
        }]
    }]
    resp = jsonify(data)
    resp.status_code = 200
    return resp

#-END-BRUSA---------------------------------------------------------------------
#=COMMANDS======================================================================

@app.route('/command/', methods=['POST'])
def recv_command():
    print(request.json())


if __name__ == '__main__':
    app.run()
