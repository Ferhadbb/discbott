from flask import Flask
from threading import Thread
import logging
import requests
import time

app = Flask('')
logger = logging.getLogger('keep_alive')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    server = Thread(target=run)
    server.daemon = True  # This ensures the thread will close when the main program ends
    server.start()
    logger.info("Keep-alive server started")

def self_ping():
    """Ping own server to prevent sleeping"""
    while True:
        try:
            requests.get("http://localhost:8080")
            logger.info("Self-ping successful")
        except Exception as e:
            logger.error(f"Self-ping failed: {e}")
        time.sleep(10 * 60)  # Ping every 10 minutes

def start_self_ping():
    ping_thread = Thread(target=self_ping)
    ping_thread.daemon = True
    ping_thread.start()
    logger.info("Self-ping thread started") 