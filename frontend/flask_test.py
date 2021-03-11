from flask import Flask, render_template, url_for
from flask import request

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
    return "{\"timestamp\": \"2020-12-01:ora\", \"state\": \"IDLE\"}"


@app.route('/handcart/errors/', methods=['GET'])
def send_errors():
    return "{\"timestamp\": \"2020-12-01:ora\", \"error code\": \"ERRORCODE01\"}"


@app.route('/handcart/warnings/', methods=['GET'])
def send_warnings():
    return "{\"timestamp\": \"2020-12-01:ora\", \"state\": \"WARNINGCODE01\"}"

if __name__ == '__main__':
    app.run()
