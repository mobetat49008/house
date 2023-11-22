from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

if __name__ == '__main__':
    # Run the application on all network interfaces, not just the loopback interface
    app.run(host='0.0.0.0', port=5000)