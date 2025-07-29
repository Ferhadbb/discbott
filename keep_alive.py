from flask import Flask
from threading import Thread
import logging
import requests
import time
import os

app = Flask('')
logger = logging.getLogger('keep_alive')

@app.route('/')
def home():
    return "Bot is alive and running!"

@app.route('/health')
def health():
    return "Healthy", 200

def run():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    server = Thread(target=run)
    server.daemon = True
    server.start()
    logger.info("Keep-alive server started")

def self_ping():
    """Ping own server to prevent sleeping"""
    render_url = os.environ.get('RENDER_EXTERNAL_URL')
    if not render_url:
        logger.warning("RENDER_EXTERNAL_URL not set, using localhost")
        render_url = "http://localhost:10000"

    while True:
        try:
            response = requests.get(f"{render_url}/health")
            if response.status_code == 200:
                logger.info("Health check successful")
            else:
                logger.warning(f"Health check returned status {response.status_code}")
        except Exception as e:
            logger.error(f"Health check failed: {e}")
        time.sleep(5 * 60)  # Check every 5 minutes

def start_self_ping():
    ping_thread = Thread(target=self_ping)
    ping_thread.daemon = True
    ping_thread.start()
    logger.info("Health check thread started") 