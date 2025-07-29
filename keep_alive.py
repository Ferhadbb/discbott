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
    """Handle OAuth and OTP callbacks from Microsoft"""
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        
        logger.info(f"Received callback with state: {state[:8]}...")
        
        if not code or not state:
            logger.error("OAuth callback missing required parameters")
            return "OAuth callback is missing required parameters (code, state).", 400
        
        if auth_manager and bot_loop:
            logger.info(f"Processing auth callback with code: {code[:5]}...")
            
            # Determine if this is an OAuth or OTP callback
            is_otp = False
            for uid, data in auth_manager.pending_otps.items():
                if data.get("flow_id") == state:
                    is_otp = True
                    break
            
            # Schedule the appropriate coroutine on the bot's event loop
            if is_otp:
                logger.info("Processing as OTP verification callback")
                future = asyncio.run_coroutine_threadsafe(
                    auth_manager.verify_otp_redirect(code, state),
                    bot_loop
                )
            else:
                logger.info("Processing as OAuth callback")
                future = asyncio.run_coroutine_threadsafe(
                    auth_manager.handle_auth_callback(code, state),
                    bot_loop
                )
            
            # Wait for a short time to catch immediate errors
            try:
                result = future.result(timeout=0.1)  # Small timeout to catch immediate errors
                logger.info(f"Auth callback scheduled successfully, immediate result: {result}")
            except asyncio.TimeoutError:
                # This is expected - the coroutine is still running
                logger.info("Auth callback processing in background")
            except Exception as e:
                logger.error(f"Error scheduling auth callback: {e}")
                # Continue anyway - we don't want to block the user
            
            return """
            <html>
                <head>
                    <title>Authentication Successful</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                        .success { color: green; font-size: 24px; margin-bottom: 20px; }
                        .info { font-size: 18px; margin-bottom: 30px; }
                    </style>
                </head>
                <body>
                    <div class="success">✅ Authentication Successful!</div>
                    <div class="info">You can now close this tab and return to Discord.</div>
                    <div>Your roles will be updated automatically.</div>
                </body>
            </html>
            """
        else:
            logger.error("Auth manager or bot event loop not initialized for callback")
            return "Bot is not ready to handle authentication. Please try again in a moment.", 503
    except Exception as e:
        logger.error(f"Error in auth_callback: {e}")
        return "An error occurred processing your authentication. Please try again.", 500

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