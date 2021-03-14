from flask import Flask, render_template, url_for, request, jsonify

app = Flask(__name__)
app.config["DEBUG"] = True

#-PAGES-------------------------------------------------------------------------

@app.route('/', methods=['GET'])
def home():
    return render_template("index.html")


@app.route('/warning')
def warning():
    return render_template("warning.html")


@app.route('/error')
def error():
    return render_template("error.html")

#-GETS--------------------------------------------------------------------------


#-HANDCART-(backend)------------------------------------------------------------

@app.route('/handcart/status/', methods=['GET'])
def get_hc_status():
    data = [{
        "timestamp": "2020-12-01:ora",
        "state": "STATE.IDLE",
        "entered": "2020-12-01:ora"
    }]
    resp = jsonify(data)
    resp.status_code = 200
    return resp


    @app.route('/handcart/errors/', methods=['GET'])
    def send_hc_errors():
        data = [{
            "timestamp": "2020-12-01:ora",
            "error code": "ERRORCODE01"
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
        "status": "STATE.TS_OFF"
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

#-BMS-VOLTAGE-DATA
@app.route('/bms-hv/volt/', methods=['GET'])
def get_bms_volt():
    data = [{
        "timestamp": "2020-12-01:ora",
        "data": [{
            "timestamp": "2020-12-01:ora",
            "volts": 304
        },
        {
            "timestamp": "2020-12-01:ora",
            "volts": 305
        },
        {
            "timestamp": "2020-12-01:ora",
            "volts": 304
        }]
    }]
    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/volt/last', methods=['GET'])
def get_last_bms_volt():
    data = [{
        "timestamp": "2020-12-01:ora",
        "volts": 305
    }]
    resp = jsonify(data)
    resp.status_code = 200
    return resp

#-BMS-AMPERE-DATA
@app.route('/bms-hv/ampere/', methods=['GET'])
def get_bms_ampere():
    data = [{
        "timestamp": "2020-12-01:ora",
        "data": [{
            "timestamp": "2020-12-01:ora",
            "amperes": 2
        },
        {
            "timestamp": "2020-12-01:ora",
            "amperes": 5
        },
        {
            "timestamp": "2020-12-01:ora",
            "amperes": 4
        }]
    }]
    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/bms-hv/ampere/last', methods=['GET'])
def get_last_bms_ampere():
    data = [{
        "timestamp": "2020-12-01:ora",
        "amperes": 4
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



@app.route('/handcart/warnings/', methods=['GET'])
def send_warnings():
    data = [{
        "timestamp": "2020-12-01:ora",
        "error code": "WARNINGCODE01"
        },
        {
        "timestamp": "2020-12-01:ora",
        "error code": "WARNINGCODE02"
    }]
    resp = jsonify(data)
    resp.status_code = 200
    return resp

#-COMMANDS----------------------------------------------------------------------

@app.route('/command/', methods=['POST'])
def recv_command():
    print(request.json())


if __name__ == '__main__':
    app.run()
