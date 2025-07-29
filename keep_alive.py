from flask import Flask, request
from threading import Thread
import logging
import requests
import time
import os
import asyncio

logger = logging.getLogger('keep_alive')

app = Flask('')
bot_loop = None
auth_manager = None

@app.route('/')
def home():
    return "FlipperBot is alive!"

@app.route('/health')
def health_check():
    return "OK", 200

@app.route('/callback')
def auth_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code or not state:
        return "OAuth callback is missing required parameters (code, state).", 400
    
    if auth_manager and bot_loop:
        # Schedule the coroutine on the bot's event loop
        asyncio.run_coroutine_threadsafe(
            auth_manager.handle_auth_callback(code, state),
            bot_loop
        )
        return "Authentication successful! You can now close this tab."
    else:
        logger.error("Auth manager or bot event loop not initialized for callback.")
        return "Bot is not ready to handle authentication. Please try again in a moment.", 503

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive(loop, manager):
    global bot_loop, auth_manager
    bot_loop = loop
    auth_manager = manager
    
    server = Thread(target=run)
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