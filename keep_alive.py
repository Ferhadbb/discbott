from flask import Flask, request
from threading import Thread
import logging
import requests
import time
import os
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger('keep_alive')

app = Flask('')
bot_loop = None
auth_manager = None

# Track callback requests to prevent abuse - More aggressive settings
callback_tracker = {}
MAX_CALLBACKS = 5  # Maximum callbacks per IP in the time window (reduced from 10)
TIME_WINDOW = 120  # Time window in seconds (increased from 60)

# Global rate limiting for all endpoints
last_request_time = datetime.now() - timedelta(seconds=5)
MIN_REQUEST_INTERVAL = 1.0  # Minimum seconds between any requests

def apply_global_rate_limit():
    """Apply a global rate limit to all requests"""
    global last_request_time
    current_time = datetime.now()
    time_since_last = (current_time - last_request_time).total_seconds()
    
    if time_since_last < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - time_since_last + 0.1)  # Add a small buffer
    
    last_request_time = datetime.now()

@app.before_request
def before_request():
    """Apply rate limiting before processing any request"""
    apply_global_rate_limit()

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
        # Rate limiting for callbacks - more aggressive
        ip = request.remote_addr
        current_time = time.time()
        
        # Initialize tracking for this IP if needed
        if ip not in callback_tracker:
            callback_tracker[ip] = []
        
        # Remove old timestamps
        callback_tracker[ip] = [ts for ts in callback_tracker[ip] if current_time - ts < TIME_WINDOW]
        
        # Check if IP is rate limited
        if len(callback_tracker[ip]) >= MAX_CALLBACKS:
            logger.warning(f"Rate limited callback from IP: {ip}")
            return "Too many requests. Please try again later.", 429
        
        # Add current timestamp
        callback_tracker[ip].append(current_time)
        
        # Get callback parameters
        code = request.args.get('code')
        state = request.args.get('state')
        
        logger.info(f"Received callback with state: {state[:8] if state else 'None'}...")
        
        if not code or not state:
            logger.error("OAuth callback missing required parameters")
            return "OAuth callback is missing required parameters (code, state).", 400
        
        if auth_manager and bot_loop:
            logger.info(f"Processing auth callback with code: {code[:5] if code else 'None'}...")
            
            # Determine if this is an OAuth or OTP callback
            is_otp = False
            for uid, data in auth_manager.pending_otps.items():
                if data.get("flow_id") == state:
                    is_otp = True
                    break
            
            # Add a small delay before processing to avoid rate limits
            time.sleep(1.0)
            
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
                # Increased timeout to allow more processing time
                result = future.result(timeout=0.5)  # Increased from 0.1
                logger.info(f"Auth callback scheduled successfully, immediate result: {result}")
            except asyncio.TimeoutError:
                # This is expected - the coroutine is still running
                logger.info("Auth callback processing in background")
            except Exception as e:
                logger.error(f"Error scheduling auth callback: {e}")
                # Continue anyway - we don't want to block the user
            
            # Add a small delay before returning the response
            time.sleep(0.5)
            
            return """
            <html>
                <head>
                    <title>Authentication Successful</title>
                    <style>
                        body { 
                            font-family: Arial, sans-serif; 
                            text-align: center; 
                            margin-top: 50px;
                            background-color: #f5f5f5;
                        }
                        .container {
                            background-color: white;
                            border-radius: 10px;
                            padding: 30px;
                            max-width: 600px;
                            margin: 0 auto;
                            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        }
                        .success { 
                            color: green; 
                            font-size: 24px; 
                            margin-bottom: 20px; 
                        }
                        .info { 
                            font-size: 18px; 
                            margin-bottom: 30px; 
                            color: #444;
                        }
                        .footer {
                            margin-top: 30px;
                            font-size: 14px;
                            color: #777;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="success">✅ Authentication Successful!</div>
                        <div class="info">You can now close this tab and return to Discord.</div>
                        <div>Your roles will be updated automatically.</div>
                        <div class="footer">FlipperBot Verification System</div>
                    </div>
                </body>
            </html>
            """
        else:
            logger.error("Auth manager or bot event loop not initialized for callback")
            return "Bot is not ready to handle authentication. Please try again in a moment.", 503
    except Exception as e:
        logger.error(f"Error in auth_callback: {e}", exc_info=True)
        return "An error occurred processing your authentication. Please try again.", 500

def run():
    # Use threaded=False to reduce potential rate limiting issues
    app.run(host='0.0.0.0', port=10000, threaded=False)

def keep_alive(loop, manager):
    global bot_loop, auth_manager
    bot_loop = loop
    auth_manager = manager
    
    server = Thread(target=run)
    server.daemon = True  # Make the thread a daemon so it exits when the main thread exits
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
            # Add a delay between pings to avoid rate limiting
            time.sleep(5 * 60)  # Check every 5 minutes
            
            response = requests.get(f"{render_url}/health")
            if response.status_code == 200:
                logger.info("Health check successful")
            else:
                logger.warning(f"Health check returned status {response.status_code}")
        except Exception as e:
            logger.error(f"Health check failed: {e}")

def start_self_ping():
    ping_thread = Thread(target=self_ping)
    ping_thread.daemon = True
    ping_thread.start()
    logger.info("Health check thread started") 