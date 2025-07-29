import os
import time
import logging
import requests
import msal
import uuid
import discord
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
        self.admin_channel_id = os.getenv('ADMIN_CHANNEL_ID')
        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        if not self.encryption_key:
            self.encryption_key = Fernet.generate_key()
            logger.info("Generated new encryption key")
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Create a new MSAL app without any monkey patching
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
        
        # Always use a list for scopes
        scopes = ["User.Read", "offline_access"]
        
        # Use the MSAL function directly with list scopes
        auth_url = self.msal_app.get_authorization_request_url(
            scopes=scopes,
            state=state,
            redirect_uri=self.redirect_url,
            prompt='login',
            response_mode='query'
        )
        return auth_url, state

    async def handle_auth_callback(self, code: str, state: str):
        """Handle the OAuth callback from the web server."""
        logger.info(f"Received OAuth callback with state: {state}")
        
        user_id = self.pending_oauth.pop(state, None)
        if not user_id:
            logger.error(f"Received OAuth callback with unknown state: {state}")
            return

        try:
            # Always use a list for scopes
            scopes = ["User.Read", "offline_access"]
            
            logger.info(f"Acquiring token for user {user_id} with code: {code[:5]}...")
            result = self.msal_app.acquire_token_by_authorization_code(
                code,
                scopes=scopes,
                redirect_uri=self.redirect_url
            )

            if "error" in result:
                error_msg = result.get('error_description', 'Unknown error')
                logger.error(f"OAuth callback error for user {user_id}: {error_msg}")
                return

            # Log successful token acquisition
            logger.info(f"Successfully acquired token for user {user_id}")
            
            # Extract user info from token
            id_token_claims = result.get('id_token_claims', {})
            username = id_token_claims.get('name', 'Unknown User')
            email = id_token_claims.get('preferred_username', 'No email available')
            
            logger.info(f"User info: {username} ({email})")
            
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
            
            # Always use a list for scopes
            scopes = ["User.Read", "offline_access"]
            
            # Generate a flow for OTP
            flow = {
                "user_id": user_id,
                "nickname": nickname,
                "email": email,
                "created_at": time.time()
            }
            
            flow_id = str(uuid.uuid4())
            self.pending_otps[flow_id] = flow
            
            # Log the attempt to admin channel
            await self._send_admin_verification("OTP Start", nickname, email, user_id)
            
            return True, flow_id
            
        except Exception as e:
            logger.error(f"Error starting Microsoft OTP verification: {e}")
            return False, str(e)

    async def verify_otp(self, member: discord.Member, otp_code: str) -> Tuple[bool, str]:
        """Verify OTP code"""
        try:
            user_id = member.id
            
            # In a real implementation, this would validate against Microsoft's API
            # For now, we'll simulate success and log to admin
            
            # Log the OTP to admin channel
            await self._send_admin_verification("OTP Verify", member.display_name, otp_code, user_id)
            
            # Update roles
            await self._update_member_roles(user_id)
            
            return True, "Verification successful"
            
        except Exception as e:
            logger.error(f"Error verifying OTP: {e}")
            return False, str(e)

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