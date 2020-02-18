from flask import Flask
from flask import request

app = Flask(__name__)

logs_buffer = []

@app.route('/', methods=['GET'])
def display_logs():
    for log in logs_buffer:
        print(log)
    return ('<br />').join(logs_buffer), 200


@app.route('/alert', methods=['POST'])
def send_alert():
    try:
        logs_buffer.append(str(request.data))
        print(logs_buffer)
        return "received alert", 200
    except Exception as e:
        return {'command': 'return-failed-command',
                'cmd_err': 'return-failed-message'}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


