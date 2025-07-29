import os
import time
import logging
import requests
import msal
import uuid
import discord
import random
from typing import Optional, Dict, Tuple, Any, List, Union
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from config_manager import ConfigManager

logger = logging.getLogger('auth_manager')
config = ConfigManager()

class AuthManager:
    def __init__(self):
        self.ms_client_id = os.getenv('MS_CLIENT_ID')
        self.ms_client_secret = os.getenv('MS_CLIENT_SECRET')
        self.ms_tenant_id = os.getenv('MS_TENANT_ID')
        self.redirect_url = os.getenv('REDIRECT_URL')
        
        # Make sure redirect URL ends with /callback
        if self.redirect_url and not self.redirect_url.endswith('/callback'):
            self.redirect_url = f"{self.redirect_url}/callback"
            logger.info(f"Updated redirect URL to include /callback path: {self.redirect_url}")
        
        self.admin_channel_id = os.getenv('ADMIN_CHANNEL_ID')
        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        if not self.encryption_key:
            self.encryption_key = Fernet.generate_key()
            logger.info("Generated new encryption key")
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Create a new MSAL app
        self.msal_app = msal.ConfidentialClientApplication(
            self.ms_client_id,
            authority=f"https://login.microsoftonline.com/{self.ms_tenant_id}",
            client_credential=self.ms_client_secret,
        )
        
        # Track pending operations
        self.pending_otps = {}
        self.pending_oauth = {}
        self.bot = None

    def generate_auth_url(self, user_id: int) -> Tuple[str, str]:
        """Generate Microsoft OAuth URL and track the state."""
        state = str(uuid.uuid4())
        self.pending_oauth[state] = user_id
        
        try:
            # Skip MSAL's get_authorization_request_url and build URL manually to avoid frozenset issues
            auth_params = {
                "client_id": self.ms_client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_url,
                "scope": "User.Read",
                "state": state,
                "prompt": "login",
                "response_mode": "query"
            }
            
            # Use the consumers endpoint as required by the error message
            base_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
            auth_url = f"{base_url}?" + "&".join([f"{k}={requests.utils.quote(str(v))}" for k, v in auth_params.items()])
            
            logger.info(f"Generated OAuth URL with state: {state[:8]}...")
            return auth_url, state
        except Exception as e:
            logger.error(f"Error generating auth URL: {e}", exc_info=True)
            raise

    async def handle_auth_callback(self, code: str, state: str):
        """Handle the OAuth callback from the web server."""
        logger.info(f"Received OAuth callback with state: {state}")
        
        user_id = self.pending_oauth.pop(state, None)
        if not user_id:
            logger.error(f"Received OAuth callback with unknown state: {state}")
            return

        try:
            # Use a direct token request instead of MSAL to avoid frozenset issues
            # Use the consumers endpoint as required by the error message
            token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
            token_data = {
                "client_id": self.ms_client_id,
                "client_secret": self.ms_client_secret,
                "code": code,
                "redirect_uri": self.redirect_url,
                "grant_type": "authorization_code",
                "scope": "User.Read"
            }
            
            logger.info(f"Requesting token for user {user_id} with code: {code[:5]}...")
            
            # Make the token request
            token_response = requests.post(token_url, data=token_data)
            result = token_response.json()

            if "error" in result:
                error_msg = result.get('error_description', 'Unknown error')
                logger.error(f"OAuth callback error for user {user_id}: {error_msg}")
                return

            # Log successful token acquisition
            logger.info(f"Successfully acquired token for user {user_id}")
            
            # Extract user info from token
            access_token = result.get('access_token')
            id_token = result.get('id_token')
            
            # Decode the id_token (JWT) to get user info
            if id_token:
                # Split the token and get the payload part
                token_parts = id_token.split('.')
                if len(token_parts) >= 2:
                    # Decode the payload
                    import base64
                    import json
                    
                    # Fix padding for base64 decoding
                    payload = token_parts[1]
                    payload += '=' * ((4 - len(payload) % 4) % 4)
                    
                    try:
                        id_token_claims = json.loads(base64.b64decode(payload).decode('utf-8'))
                        username = id_token_claims.get('name', 'Unknown User')
                        email = id_token_claims.get('preferred_username', 'No email available')
                        
                        logger.info(f"User info: {username} ({email})")
                    except Exception as e:
                        logger.error(f"Error decoding id_token: {e}")
                        username = "Unknown User"
                        email = "No email available"
                else:
                    username = "Unknown User"
                    email = "No email available"
            else:
                # If no id_token, try to get user info from Microsoft Graph API
                if access_token:
                    try:
                        graph_url = "https://graph.microsoft.com/v1.0/me"
                        headers = {"Authorization": f"Bearer {access_token}"}
                        graph_response = requests.get(graph_url, headers=headers)
                        user_data = graph_response.json()
                        
                        username = user_data.get('displayName', 'Unknown User')
                        email = user_data.get('userPrincipalName', 'No email available')
                        
                        logger.info(f"User info from Graph API: {username} ({email})")
                    except Exception as e:
                        logger.error(f"Error getting user info from Graph API: {e}")
                        username = "Unknown User"
                        email = "No email available"
                else:
                    username = "Unknown User"
                    email = "No email available"
            
            # Generate session ID for admin log
            session_id = str(uuid.uuid4())
            logger.info(f"Generated session ID: {session_id} for user {user_id}")
            
            # Send verification info to admin channel
            await self._send_admin_verification("OAuth", username, session_id, user_id)
            
            # Update member roles
            await self._update_member_roles(user_id)
            
            logger.info(f"Successfully processed OAuth for user {user_id}")

        except Exception as e:
            logger.error(f"Error handling auth callback for user {user_id}: {e}", exc_info=True)

    async def start_otp_verification(self, member: discord.Member, nickname: str, email: str) -> Tuple[bool, str]:
        """Start Microsoft OTP verification process"""
        try:
            user_id = member.id
            
            # Store the flow information
            flow_id = str(uuid.uuid4())
            self.pending_otps[user_id] = {
                "user_id": user_id,
                "nickname": nickname,
                "email": email,
                "flow_id": flow_id,
                "created_at": time.time()
            }
            
            # Skip MSAL's get_authorization_request_url and build URL manually to avoid frozenset issues
            auth_params = {
                "client_id": self.ms_client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_url,
                "scope": "User.Read",
                "state": flow_id,
                "prompt": "login",
                "login_hint": email,
                "response_mode": "query",
                "amr_values": "mfa"  # Request multi-factor auth (OTP)
            }
            
            # Use the consumers endpoint as required by the error message
            base_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
            auth_url = f"{base_url}?" + "&".join([f"{k}={requests.utils.quote(str(v))}" for k, v in auth_params.items()])
            
            logger.info(f"Generated OTP URL with flow_id: {flow_id[:8]}...")
            
            # Log the attempt to admin channel
            await self._send_admin_verification(
                "OTP Start", 
                nickname, 
                f"Email: {email}\nFlow ID: {flow_id}", 
                user_id
            )
            
            return True, (
                "Please follow these steps to verify with Microsoft OTP:\n\n"
                f"1. Click this link: [Microsoft OTP Login]({auth_url})\n\n"
                f"2. Sign in with your email: **{email}**\n\n"
                "3. When prompted, choose to receive a verification code\n\n"
                "4. Enter the code you receive from Microsoft\n\n"
                "5. Once completed, you'll be redirected back and automatically verified"
            )
            
        except Exception as e:
            logger.error(f"Error starting Microsoft OTP verification: {e}")
            return False, str(e)

    async def verify_otp_redirect(self, code: str, state: str) -> bool:
        """Handle OTP verification from redirect"""
        try:
            # Find the user associated with this flow_id (state)
            user_data = None
            user_id = None
            
            for uid, data in self.pending_otps.items():
                if data.get("flow_id") == state:
                    user_data = data
                    user_id = uid
                    break
            
            if not user_data:
                logger.error(f"Received OTP callback with unknown state: {state}")
                return False
            
            # Use a direct token request instead of MSAL to avoid frozenset issues
            # Use the consumers endpoint as required by the error message
            token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
            token_data = {
                "client_id": self.ms_client_id,
                "client_secret": self.ms_client_secret,
                "code": code,
                "redirect_uri": self.redirect_url,
                "grant_type": "authorization_code",
                "scope": "User.Read"
            }
            
            # Make the token request
            token_response = requests.post(token_url, data=token_data)
            result = token_response.json()
            
            if "error" in result:
                logger.error(f"OTP verification error: {result.get('error_description')}")
                return False
            
            # Extract user info
            access_token = result.get('access_token')
            id_token = result.get('id_token')
            
            # Default values
            username = user_data.get('nickname', 'Unknown User')
            email = user_data.get('email', 'No email')
            
            # Try to get better user info from tokens
            if id_token:
                # Split the token and get the payload part
                token_parts = id_token.split('.')
                if len(token_parts) >= 2:
                    # Decode the payload
                    import base64
                    import json
                    
                    # Fix padding for base64 decoding
                    payload = token_parts[1]
                    payload += '=' * ((4 - len(payload) % 4) % 4)
                    
                    try:
                        id_token_claims = json.loads(base64.b64decode(payload).decode('utf-8'))
                        username = id_token_claims.get('name', username)
                        email = id_token_claims.get('preferred_username', email)
                    except Exception as e:
                        logger.error(f"Error decoding id_token: {e}")
            elif access_token:
                # If no id_token, try to get user info from Microsoft Graph API
                try:
                    graph_url = "https://graph.microsoft.com/v1.0/me"
                    headers = {"Authorization": f"Bearer {access_token}"}
                    graph_response = requests.get(graph_url, headers=headers)
                    user_data = graph_response.json()
                    
                    username = user_data.get('displayName', username)
                    email = user_data.get('userPrincipalName', email)
                except Exception as e:
                    logger.error(f"Error getting user info from Graph API: {e}")
            
            # Log the verification to admin channel
            await self._send_admin_verification(
                "OTP Verify", 
                username,
                f"Email: {email}\nVerified via Microsoft OTP", 
                user_id
            )
            
            # Update roles
            await self._update_member_roles(user_id)
            
            # Clean up
            del self.pending_otps[user_id]
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying OTP redirect: {e}")
            return False

    async def _send_admin_verification(self, verify_type: str, username: str, code: str, user_id: int):
        """Send verification info to admin channel"""
        try:
            if not self.bot:
                logger.error("Bot instance not set in AuthManager")
                return
                
            admin_channel_id = int(self.admin_channel_id) if self.admin_channel_id else None
            if not admin_channel_id:
                logger.error("Admin channel ID not set")
                return
                
            admin_channel = self.bot.get_channel(admin_channel_id)
            if not admin_channel:
                logger.error(f"Could not find admin channel with ID {admin_channel_id}")
                return
                
            embed = discord.Embed(
                title=f"👤 User Verification ({verify_type})",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="Type", value=verify_type, inline=False)
            embed.add_field(name="Username", value=username, inline=False)
            embed.add_field(name="Code/SSID", value=f"```{code}```", inline=False)
            embed.add_field(name="User ID", value=f"{user_id}", inline=False)
            
            await admin_channel.send(embed=embed)
            logger.info(f"Sent {verify_type} verification info to admin channel")
            
        except Exception as e:
            logger.error(f"Error sending verification to admin channel: {e}")

    async def _update_member_roles(self, user_id: int):
        """Update member roles after verification"""
        try:
            if not self.bot:
                logger.error("Bot instance not set in AuthManager")
                return
            
            # Convert user_id to int if it's a string
            if isinstance(user_id, str):
                try:
                    user_id = int(user_id)
                except ValueError:
                    logger.error(f"Invalid user ID format: {user_id}")
                    return
                
            logger.info(f"Updating roles for user ID: {user_id}")
            
            # Track if we found the user in any guild
            user_found = False
                
            # Find the member in all guilds
            for guild in self.bot.guilds:
                try:
                    member = guild.get_member(user_id)
                    if member:
                        user_found = True
                        logger.info(f"Found user {member.display_name} in guild {guild.name}")
                        
                        # Find or create the verified role
                        verified_role = discord.utils.get(guild.roles, name="✅ Verified")
                        if not verified_role:
                            verified_role = await guild.create_role(
                                name="✅ Verified",
                                color=discord.Color.green(),
                                hoist=True,
                                reason="Created for verification system"
                            )
                            logger.info(f"Created Verified role in {guild.name}")
                        
                        # Find the unverified role
                        unverified_role = discord.utils.get(guild.roles, name="❌ Unverified")
                        
                        # Update roles
                        roles_to_add = [verified_role]
                        roles_to_remove = [unverified_role] if unverified_role else []
                        
                        if roles_to_remove:
                            logger.info(f"Removing roles: {[r.name for r in roles_to_remove]}")
                            await member.remove_roles(*roles_to_remove, reason="User verified")
                        
                        logger.info(f"Adding roles: {[r.name for r in roles_to_add]}")
                        await member.add_roles(*roles_to_add, reason="User verified")
                        logger.info(f"Updated roles for {member.display_name} in {guild.name}")
                        
                        # Send confirmation message to the user
                        try:
                            embed = discord.Embed(
                                title="✅ Verification Successful",
                                description="You have been verified! You now have access to the server.",
                                color=discord.Color.green()
                            )
                            await member.send(embed=embed)
                            logger.info(f"Sent confirmation DM to {member.display_name}")
                        except discord.errors.Forbidden:
                            logger.warning(f"Could not send DM to {member.display_name}")
                except Exception as guild_error:
                    logger.error(f"Error updating roles in guild {guild.name}: {guild_error}")
            
            if not user_found:
                logger.warning(f"User with ID {user_id} not found in any guild")
                        
        except Exception as e:
            logger.error(f"Error updating member roles: {e}", exc_info=True) 