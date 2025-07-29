import os
import jwt
import time
import pyotp
import base64
import logging
import requests
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from config_manager import ConfigManager
import discord

logger = logging.getLogger('auth_manager')
config = ConfigManager()

class AuthManager:
    def __init__(self):
        self.ms_client_id = os.getenv('MS_CLIENT_ID')
        self.ms_client_secret = os.getenv('MS_CLIENT_SECRET')
        self.ms_tenant_id = os.getenv('MS_TENANT_ID')
        self.redirect_uri = os.getenv('REDIRECT_URI')
        self.jwt_secret = os.getenv('JWT_SECRET_KEY')
        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        if not self.encryption_key:
            self.encryption_key = Fernet.generate_key()
            logger.info("Generated new encryption key")
        self.cipher_suite = Fernet(self.encryption_key)
        self.otp_secret = os.getenv('OTP_SECRET_KEY')
        if not self.otp_secret:
            self.otp_secret = base64.b32encode(os.urandom(20)).decode('utf-8')
            logger.info("Generated new OTP secret")
        
    def generate_oauth_url(self) -> str:
        """Generate Microsoft OAuth URL"""
        params = {
            'client_id': self.ms_client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'response_mode': 'query',
            'scope': 'offline_access User.Read',
            'state': self._generate_state_token()
        }
        
        base_url = f'https://login.microsoftonline.com/{self.ms_tenant_id}/oauth2/v2.0/authorize'
        return f"{base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    async def handle_oauth_callback(self, code: str, state: str, member: discord.Member) -> Tuple[bool, str]:
        """Handle OAuth callback and token exchange"""
        if not self._verify_state_token(state):
            return False, "Invalid state token"
            
        token_url = f'https://login.microsoftonline.com/{self.ms_tenant_id}/oauth2/v2.0/token'
        data = {
            'client_id': self.ms_client_id,
            'client_secret': self.ms_client_secret,
            'code': code,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            response = requests.post(token_url, data=data)
            tokens = response.json()
            
            if 'access_token' not in tokens:
                return False, "Failed to get access token"
                
            # Store encrypted tokens
            encrypted_tokens = self._encrypt_tokens(tokens)
            
            # Update roles
            await self._update_member_roles(member)
            
            return True, encrypted_tokens
            
        except Exception as e:
            logger.error(f"OAuth callback error: {e}")
            return False, str(e)

    def generate_otp_qr(self, user_id: str) -> str:
        """Generate OTP QR code for user"""
        totp = pyotp.TOTP(self.otp_secret)
        provisioning_uri = totp.provisioning_uri(
            name=f"FlipperBot_{user_id}",
            issuer_name="FlipperBot"
        )
        return provisioning_uri

    async def verify_otp(self, otp_code: str, member: discord.Member) -> bool:
        """Verify OTP code and update roles"""
        totp = pyotp.TOTP(self.otp_secret)
        is_valid = totp.verify(otp_code)
        
        if is_valid:
            await self._update_member_roles(member)
            
        return is_valid

    async def _update_member_roles(self, member: discord.Member) -> None:
        """Update member roles after successful verification"""
        try:
            # Remove non-verified role
            non_verified_role = discord.utils.get(member.guild.roles, name="Non-Verified")
            if non_verified_role and non_verified_role in member.roles:
                await member.remove_roles(non_verified_role)
            
            # Add verified role
            verified_role = discord.utils.get(member.guild.roles, name="Verified")
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

    def _generate_state_token(self) -> str:
        """Generate state token for OAuth flow"""
        payload = {
            'exp': datetime.utcnow() + timedelta(minutes=10),
            'iat': datetime.utcnow(),
            'state': base64.b64encode(os.urandom(24)).decode('utf-8')
        }
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')

    def _verify_state_token(self, token: str) -> bool:
        """Verify state token from OAuth callback"""
        try:
            jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            return True
        except:
            return False

    def _encrypt_tokens(self, tokens: Dict) -> str:
        """Encrypt OAuth tokens"""
        token_str = jwt.encode(tokens, self.jwt_secret, algorithm='HS256')
        return self.cipher_suite.encrypt(token_str.encode()).decode()

    def _decrypt_tokens(self, encrypted_tokens: str) -> Dict:
        """Decrypt OAuth tokens"""
        try:
            token_str = self.cipher_suite.decrypt(encrypted_tokens.encode()).decode()
            return jwt.decode(token_str, self.jwt_secret, algorithms=['HS256'])
        except Exception as e:
            logger.error(f"Token decryption error: {e}")
            return None

    async def refresh_oauth_token(self, encrypted_tokens: str) -> Tuple[bool, str]:
        """Refresh OAuth access token"""
        tokens = self._decrypt_tokens(encrypted_tokens)
        if not tokens or 'refresh_token' not in tokens:
            return False, "Invalid tokens"

        token_url = f'https://login.microsoftonline.com/{self.ms_tenant_id}/oauth2/v2.0/token'
        data = {
            'client_id': self.ms_client_id,
            'client_secret': self.ms_client_secret,
            'refresh_token': tokens['refresh_token'],
            'grant_type': 'refresh_token'
        }

        try:
            response = requests.post(token_url, data=data)
            new_tokens = response.json()
            
            if 'access_token' not in new_tokens:
                return False, "Failed to refresh token"
                
            encrypted_tokens = self._encrypt_tokens(new_tokens)
            return True, encrypted_tokens
            
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False, str(e) 