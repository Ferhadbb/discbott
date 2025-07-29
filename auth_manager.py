import os
import json
import base64
import secrets
from datetime import datetime, timedelta
import pyotp
from cryptography.fernet import Fernet
from msal import ConfidentialClientApplication
from dotenv import load_dotenv

load_dotenv()

class AuthManager:
    def __init__(self):
        # Initialize encryption key
        self.encryption_key = os.getenv('ENCRYPTION_KEY') or Fernet.generate_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
        # In-memory storage
        self.users = {}
        
        # Microsoft OAuth setup
        self.ms_client = ConfidentialClientApplication(
            os.getenv('MICROSOFT_CLIENT_ID'),
            authority="https://login.microsoftonline.com/consumers",
            client_credential=os.getenv('MICROSOFT_CLIENT_SECRET')
        )
        
        # OAuth configuration
        self.redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:8000/callback')
        self.scopes = ["XboxLive.signin"]
        
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.cipher_suite.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
    
    def generate_otp_secret(self) -> str:
        """Generate a new OTP secret"""
        return pyotp.random_base32()
    
    def verify_otp(self, secret: str, otp: str) -> bool:
        """Verify OTP code"""
        totp = pyotp.TOTP(secret)
        return totp.verify(otp)
    
    def get_oauth_url(self, state: str = None) -> str:
        """Get Microsoft OAuth URL"""
        if not state:
            state = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        auth_url = self.ms_client.get_authorization_request_url(
            scopes=self.scopes,
            state=state,
            redirect_uri=self.redirect_uri
        )
        return auth_url, state
    
    async def process_oauth_callback(self, code: str) -> dict:
        """Process OAuth callback and get Microsoft account info"""
        result = await self.ms_client.acquire_token_by_authorization_code(
            code,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        return result
    
    async def store_user_credentials(self, discord_id: str, auth_type: str, **credentials):
        """Store user credentials in memory"""
        # Encrypt sensitive data
        encrypted_data = {}
        if auth_type == 'microsoft':
            encrypted_data = {
                'access_token': self.encrypt_data(credentials['access_token']),
                'refresh_token': self.encrypt_data(credentials['refresh_token'])
            }
        else:  # manual login
            encrypted_data = {
                'email': self.encrypt_data(credentials['email']),
                'password': self.encrypt_data(credentials['password']),
                'otp_secret': credentials['otp_secret']
            }
        
        # Store in memory
        self.users[discord_id] = {
            'auth_type': auth_type,
            'credentials': encrypted_data,
            'created_at': datetime.utcnow(),
            'last_updated': datetime.utcnow()
        }
        
        return self.users[discord_id]
    
    async def get_user_credentials(self, discord_id: str) -> dict:
        """Retrieve user credentials from memory"""
        user = self.users.get(discord_id)
        if not user:
            return None
            
        # Decrypt sensitive data
        decrypted_credentials = {}
        if user['auth_type'] == 'microsoft':
            decrypted_credentials = {
                'access_token': self.decrypt_data(user['credentials']['access_token']),
                'refresh_token': self.decrypt_data(user['credentials']['refresh_token'])
            }
        else:
            decrypted_credentials = {
                'email': self.decrypt_data(user['credentials']['email']),
                'password': self.decrypt_data(user['credentials']['password']),
                'otp_secret': user['credentials']['otp_secret']
            }
            
        return {
            'auth_type': user['auth_type'],
            'credentials': decrypted_credentials
        }
    
    async def delete_user_data(self, discord_id: str) -> bool:
        """Delete user data from memory"""
        if discord_id in self.users:
            del self.users[discord_id]
            return True
        return False
    
    def generate_qr_code_url(self, secret: str, username: str) -> str:
        """Generate QR code URL for OTP setup"""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(username, issuer_name="MC Flipper Bot") 