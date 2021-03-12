from flask import Flask, render_template, url_for, request, jsonify

app = Flask(__name__)
app.config["DEBUG"] = True

# pages

@app.route('/', methods=['GET'])
def home():
    return render_template("index.html")

@app.route('/warning')
def warning():
    return render_template("warning.html")

@app.route('/error')
def error():
    return render_template("error.html")

@app.route('/command/', methods=['POST'])
def recv_command():
    print(request.json())


@app.route('/handcart/status/', methods=['GET'])
def send_status():
    data = {
        "timestamp": "2020-12-01:ora",
        "state": "IDLE"
    }
    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/handcart/errors/', methods=['GET'])
def send_errors():
    data = {
        "timestamp": "2020-12-01:ora",
        "error code": "ERRORCODE01"
    }
    resp = jsonify(data)
    resp.status_code = 200
    return resp


@app.route('/handcart/warnings/', methods=['GET'])
def send_warnings():
    data = {
        "timestamp": "2020-12-01:ora",
        "error code": "WARNINGCODE01"
    }
    resp = jsonify(data)
    resp.status_code = 200
    return resp

if __name__ == '__main__':
    app.run()
