import flask
from flask import request

app = flask.Flask(__name__)
app.config["DEBUG"] = True


@app.route('/', methods=['GET'])
def home():
    return flask.render_template("index.html")


@app.route('/command/', methods=['POST'])
def recv_command():
    print(request.json())


@app.route('/handcart/status/', methods=['GET'])
def send_status():
    return "{\"timestamp\": \"2020-12-01:ora\", \"state\": \"IDLE\"}"


app.run()
