import json
import logging
from datetime import datetime, timedelta

import flask
import pytz
from flask import render_template, jsonify, request

from can_eagle.lib.primary.python.network import HvErrors
from common.accumulator.bms import ACCUMULATOR


def thread_3_WEB(shared_data, lock, com_queue):
    """
    The webserver thread that runs the server serving the RESFUL requests
    :return:
    """
    app = flask.Flask(__name__)
    app.config["DEBUG"] = False
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    @app.route('/', methods=['GET'])
    def home():
        return render_template("index.html")

    @app.route('/warnings')
    def warnings():
        return render_template("warning.html")

    @app.route('/errors')
    def errors():
        return render_template("error.html")

    @app.route('/settings')
    def settings():
        return render_template("settings.html")

    @app.route('/charts')
    def charts():
        chart = request.args.get("chart")
        return render_template("charts.html", c=chart)

    @app.route('/brusa-info')
    def brusa_info():
        return render_template("brusa-info.html")

    def getLastNSeconds(n):
        now = datetime.now(pytz.timezone('Europe/Rome'))
        a = [(now - timedelta(seconds=i)) for i in range(n)]
        a.reverse()  # an array with the last n seconds form the older date to the now date

        return a

    # HANDCART-(backend)------------------------------------------------------------

    @app.route('/handcart/status', methods=['GET'])
    def get_hc_status():
        with lock:
            data = {
                "timestamp": datetime.now().isoformat(),
                "state": str(shared_data.FSM_stat.name),
                "entered": shared_data.FSM_entered_stat
            }
            resp = jsonify(data)
            resp.status_code = 200
            return resp

    @app.route('/handcart/charged', methods=['GET'])
    def send_hc_charged():
        with lock:
            data = {
                "timestamp": datetime.now().isoformat(),
                "charged_brusa_wh": shared_data.brusa.charged_capacity_wh,
                "charged_brusa_ah": shared_data.brusa.charged_capacity_ah,
                "charged_bms_hv_ah": shared_data.bms_hv.charged_capacity_ah,
                "charged_bms_hv_wh": shared_data.bms_hv.charged_capacity_wh
            }
            resp = jsonify(data)
            resp.status_code = 200
            return resp

    # END-HANDCART-(backend)--------------------------------------------------------
    # BMS-HV------------------------------------------------------------------------

    @app.route('/bms-hv/status', methods=['GET'])
    def get_bms_hv_status():
        with lock:
            if shared_data.bms_hv.isConnected():
                res = {
                    "timestamp": shared_data.bms_hv.lastupdated,
                    "status": shared_data.bms_hv.status.name,
                    "accumulator": shared_data.bms_hv.ACC_CONNECTED.value,
                    "fans_override_status": shared_data.bms_hv.fans_override_status,
                    "fans_override_speed": shared_data.bms_hv.fans_override_speed
                }
                res = jsonify(res)
            else:
                res = {
                    "timestamp": shared_data.bms_hv.lastupdated,
                    "status": "OFFLINE",
                    "accumulator": -1,
                    "fans_override_status": False,
                    "fans_override_speed": 0
                }
                res = jsonify(res)
                res.status_code = 450
        return res

    @app.route('/bms-hv/errors', methods=['GET'])
    def get_bms_hv_errors():
        with lock:
            if shared_data.bms_hv.isConnected():
                error_list = []

                if shared_data.bms_hv.ACC_CONNECTED == ACCUMULATOR.FENICE:
                    for i in HvErrors:
                        if HvErrors(i) in HvErrors(shared_data.bms_hv.errors):
                            error_list.append(HvErrors(i).name)
                elif shared_data.bms_hv.ACC_CONNECTED == ACCUMULATOR.CHIMERA:
                    error_list = shared_data.bms_hv.error_list_chimera

                res = {
                    "timestamp": shared_data.bms_hv.lastupdated,
                    "errors": error_list
                }
                res = jsonify(res)
            else:
                res = jsonify("not connected")
                res.status_code = 450
        return res

    @app.route('/bms-hv/warnings', methods=['GET'])
    def get_bms_hv_warnings():
        data = {
            "timestamp": datetime.now().isoformat(),
            "warnings": []
        }

        resp = jsonify(data)
        resp.status_code = 200
        return resp

    # BMS-VOLTAGE-DATA
    @app.route('/bms-hv/volt', methods=['GET'])
    def get_bms_hv_volt():
        args = request.args
        args.to_dict()

        try:
            f = int(args.get("from"))
            t = int(args.get("to"))
        except (ValueError, TypeError):
            resp = jsonify("Error in request arguments")
            resp.status_code = 400
            return resp

        if shared_data.bms_hv.isConnected():
            timestamp = datetime.now(pytz.timezone('Europe/Rome'))

            if f < 0 or f > t or t < 0:
                resp = jsonify("JSON index error in request")
                resp.status_code = 400
                return resp

            data = {"timestamp": timestamp.isoformat(),
                    "remaining": 0}

            if f > shared_data.bms_hv.hv_voltage_history_index:
                data["data"] = []
            elif t > shared_data.bms_hv.hv_voltage_history_index:
                data["data"] = shared_data.bms_hv.hv_voltage_history[f:shared_data.bms_hv.hv_voltage_history_index]
            else:
                data["data"] = shared_data.bms_hv.hv_voltage_history[f:t]
                data["remaining"] = shared_data.bms_hv.hv_voltage_history_index - t

            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("not connected")
            resp.status_code = 450
        return resp

    @app.route('/bms-hv/volt/last', methods=['GET'])
    def get_last_bms_hv_volt():
        if shared_data.bms_hv.isConnected():
            data = {
                "timestamp": shared_data.bms_hv.lastupdated,
                "pack_voltage": shared_data.bms_hv.act_bus_voltage,
                "bus_voltage": shared_data.bms_hv.act_bus_voltage,
                "max_cell_voltage": shared_data.bms_hv.max_cell_voltage,
                "min_cell_voltage": shared_data.bms_hv.min_cell_voltage,
                "index": shared_data.bms_hv.hv_voltage_history_index
            }
            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("bms hv is offline")
            resp.status_code = 450
        return resp

    @app.route('/bms-hv/ampere', methods=['GET'])
    def get_bms_hv_ampere():
        args = request.args
        args.to_dict()

        try:
            f = int(args.get("from"))
            t = int(args.get("to"))
        except (ValueError, TypeError):
            resp = jsonify("Error in request arguments")
            resp.status_code = 400
            return resp

        if shared_data.bms_hv.isConnected():
            timestamp = datetime.now(pytz.timezone('Europe/Rome'))

            if f < 0 or f > t or t < 0:
                resp = jsonify("JSON index error in request")
                resp.status_code = 400
                return resp

            data = {"timestamp": timestamp.isoformat(),
                    "remaining": 0}

            if f > shared_data.bms_hv.hv_current_history_index:
                data["data"] = []
            elif t > shared_data.bms_hv.hv_current_history_index:
                data["data"] = shared_data.bms_hv.hv_current_history[f:shared_data.bms_hv.hv_current_history_index]
            else:
                data["data"] = shared_data.bms_hv.hv_current_history[f:t]
                data["remaining"] = shared_data.bms_hv.hv_current_history_index - t

            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("not connected")
            resp.status_code = 450
        return resp

    @app.route('/bms-hv/ampere/last', methods=['GET'])
    def get_last_bms_hv_ampere():
        if shared_data.bms_hv.isConnected():
            data = {
                "timestamp": shared_data.bms_hv.lastupdated,
                "current": shared_data.bms_hv.act_current,
                "power": shared_data.bms_hv.act_power,
                "index": shared_data.bms_hv.hv_current_history_index
            }

            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("not connected")
            resp.status_code = 450
        return resp

    # BMS-TEMPERATURE-DATA
    @app.route('/bms-hv/temp', methods=['GET'])
    def get_bms_temp():
        args = request.args
        args.to_dict()

        try:
            f = int(args.get("from"))
            t = int(args.get("to"))
        except (ValueError, TypeError):
            resp = jsonify("Error in request arguments")
            resp.status_code = 400
            return resp

        if shared_data.bms_hv.isConnected():
            timestamp = datetime.now(pytz.timezone('Europe/Rome'))

            if f < 0 or f > t or t < 0:
                resp = jsonify("JSON index error in request")
                resp.status_code = 400
                return resp

            data = {"timestamp": timestamp.isoformat(),
                    "remaining": 0}

            if f > shared_data.bms_hv.hv_temp_history_index:
                data["data"] = []
            elif t > shared_data.bms_hv.hv_temp_history_index:
                data["data"] = shared_data.bms_hv.hv_temp_history[f:shared_data.bms_hv.hv_temp_history_index]
            else:
                data["data"] = shared_data.bms_hv.hv_temp_history[f:t]
                data["remaining"] = shared_data.bms_hv.hv_temp_history_index - t

            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("not connected")
            resp.status_code = 450
        return resp

    @app.route('/bms-hv/temp/last', methods=['GET'])
    def get_last_bms_temp():
        if shared_data.bms_hv.isConnected():
            data = {
                "timestamp": shared_data.bms_hv.lastupdated,
                "average_temp": shared_data.bms_hv.act_average_temp,
                "max_temp": shared_data.bms_hv.max_temp,
                "min_temp": shared_data.bms_hv.min_temp,
                "index": shared_data.bms_hv.hv_temp_history_index
            }
            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("bms hv is not connected")
            resp.status_code = 450
        return resp

    # BMS-CELLS-DATA
    @app.route('/bms-hv/cells/voltage', methods=['GET'])
    def get_bms_cells():
        # Indice assoluto rispetto a tutte le celle
        data = {
            "timestamp": "2020-12-01:ora",
            "data": []
        }
        resp = jsonify(data)

        resp.status_code = 200
        return resp

    @app.route('/bms-hv/cells/voltage/last', methods=['GET'])
    def get_last_bms_cells():
        if shared_data.bms_hv.ACC_CONNECTED == ACCUMULATOR.FENICE and shared_data.bms_hv.isConnected():
            timestamp = datetime.now(pytz.timezone('Europe/Rome'))

            cells = []

            for i, c in enumerate(shared_data.bms_hv.hv_cells_act):
                cells.append({
                    "id": i,
                    "voltage": c
                })

            data = {
                "timestamp": timestamp,
                "cells": cells
            }

            resp = jsonify(data)
            resp.status_code = 200
            return resp
        else:
            resp = jsonify("not connected")
            resp.status_code = 450
            return resp

    @app.route('/bms-hv/cells/temp/last', methods=['GET'])
    def get_bms_heat():
        if shared_data.bms_hv.ACC_CONNECTED == ACCUMULATOR.FENICE and shared_data.bms_hv.isConnected():
            timestamp = datetime.now(pytz.timezone('Europe/Rome'))

            cells = []

            for i, t in enumerate(shared_data.bms_hv.hv_temps_act):
                cells.append({
                    "id": i,
                    "temp": t
                })

            data = {
                "timestamp": timestamp,
                "cells": cells
            }

            resp = jsonify(data)
            resp.status_code = 200
            return resp
        else:
            resp = jsonify("not connected")
            resp.status_code = 450
            return resp

    # END-BMS-HV--------------------------------------------------------------------
    # BRUSA-------------------------------------------------------------------------

    @app.route('/brusa/status', methods=['GET'])
    def get_brusa_status():
        with lock:
            if shared_data.brusa.isConnected():
                res = {
                    "timestamp": shared_data.brusa.lastupdated,
                    "status": shared_data.brusa.act_NLG5_ST_values
                }

                res = jsonify(res)
            else:
                res = jsonify(
                    {
                        "timestamp": shared_data.brusa.lastupdated,
                        "status": {}
                    }
                )
                res.status_code = 450
        return res

    @app.route('/brusa/errors', methods=['GET'])
    def get_brusa_errors():
        with lock:
            if not shared_data.brusa.isConnected():
                res = jsonify("not connected")
                res.status_code = 450
                return res

            errorList = shared_data.brusa.act_NLG5_ERR_str
            res = {"timestamp": shared_data.brusa.lastupdated, "errors": errorList}
            return jsonify(res)

    @app.route('/brusa/info', methods=['GET'])
    def get_brusa_info():
        with lock:
            if not shared_data.brusa.isConnected():
                res = jsonify("not connected")
                res.status_code = 450
                return res

            res = {
                "timestamp": shared_data.brusa.lastupdated,
            }
            if shared_data.brusa.act_NLG5_ACT_I != {}:
                res["NLG5_MC_ACT"] = round(shared_data.brusa.act_NLG5_ACT_I['NLG5_MC_ACT'], 2)
                res["NLG5_MV_ACT"] = round(shared_data.brusa.act_NLG5_ACT_I['NLG5_MV_ACT'], 2)
                res["NLG5_OV_ACT"] = round(shared_data.brusa.act_NLG5_ACT_I['NLG5_OV_ACT'], 2)
                res["NLG5_OC_ACT"] = round(shared_data.brusa.act_NLG5_ACT_I['NLG5_OC_ACT'], 2)
            else:
                res["NLG5_MC_ACT"] = 0
                res["NLG5_MV_ACT"] = 0
                res["NLG5_OV_ACT"] = 0
                res["NLG5_OC_ACT"] = 0
            if shared_data.brusa.act_NLG5_ACT_II != {}:
                res["NLG5_S_MC_M_CP"] = round(shared_data.brusa.act_NLG5_ACT_II['NLG5_S_MC_M_CP'], 2)
            else:
                res["NLG5_S_MC_M_CP"] = 0

            if shared_data.brusa.act_NLG5_TEMP != {}:
                res["NLG5_P_TMP"] = round(shared_data.brusa.act_NLG5_TEMP['NLG5_P_TMP'], 2)
            else:
                res["NLG5_P_TMP"] = 0

            return jsonify(res)

    @app.route('/command/setting', methods=['GET'])
    def send_settings_command():
        with lock:
            # print(request.get_json())
            data = [{
                "com-type": "cutoff",
                "value": shared_data.target_v
            }, {
                "com-type": "fast-charge",
                "value": False
            }, {
                "com-type": "max-in-current",
                "value": shared_data.act_set_in_current
            }, {
                "com-type": "max-out-current",
                "value": shared_data.act_set_out_current
            }, {
                "com-type": "fan-override-set-status",
                "value": shared_data.bms_hv.fans_set_override_status
            }, {
                "com-type": "fan-override-set-speed",
                "value": shared_data.bms_hv.fans_set_override_speed
            }]

            resp = jsonify(data)
            resp.status_code = 200
            return resp

    @app.route('/command/setting', methods=['POST'])
    def recv_command_setting():
        # print(request.get_json())
        command = request.get_json()
        if type(command) != dict:
            command = json.loads(command)
        # in this method and the below one there's
        com_queue.put(command)  # an error due to json is a dict not a string

        resp = jsonify(success=True)
        return resp

    @app.route('/command/action', methods=['POST'])
    def recv_command_action():
        # print(request.get_json())
        action = request.get_json()
        if type(action) != dict:
            action = json.loads(action)

        com_queue.put(action)  # same error above

        resp = jsonify(success=True)
        return resp

    # app.run(use_reloader=False)
    app.run(use_reloader=False, host="0.0.0.0", port=8080)  # to run on the pc ip
