import yaml
import os
import logging
from typing import Any, Dict, List, Optional, Union
from cryptography.fernet import Fernet
import re

logger = logging.getLogger('config_manager')

class ConfigManager:
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def __init__(self, config_path: str = 'config.yaml'):
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            else:
                logger.warning(f"Config file {self.config_path} not found. Loading default config.")
                default_path = 'config_default.yaml'
                if os.path.exists(default_path):
                    with open(default_path, 'r', encoding='utf-8') as f:
                        return yaml.safe_load(f) or {}
                return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

    def _process_env_vars(self, config: Dict):
        """Recursively process environment variables in config"""
        for key, value in config.items():
            if isinstance(value, dict):
                self._process_env_vars(value)
            elif isinstance(value, str):
                # Check for ${VAR} pattern
                matches = re.findall(r'\${([^}]+)}', value)
                if matches:
                    for var_name in matches:
                        env_value = os.getenv(var_name)
                        if env_value:
                            config[key] = env_value
                        else:
                            logger.warning(f"Environment variable {var_name} not found")
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get(self, path: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation."""
        try:
            value = self.config
            for key in path.split('.'):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, path: str, value: Any) -> None:
        """Set a configuration value using dot notation."""
        keys = path.split('.')
        current = self.config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        self._save_config()

    def add_to_list(self, path: str, value: Any) -> bool:
        """Add a value to a list in the configuration"""
        try:
            current_list = self.get(path, [])
            if not isinstance(current_list, list):
                current_list = []
            
            if value not in current_list:
                current_list.append(value)
                self.set(path, current_list)
                return True
            return False
        except Exception as e:
            logger.error(f"Error adding to list: {e}")
            return False
    
    def remove_from_list(self, path: str, value: Any) -> bool:
        """Remove a value from a list in the configuration"""
        try:
            current_list = self.get(path, [])
            if not isinstance(current_list, list):
                return False
            
            if value in current_list:
                current_list.remove(value)
                self.set(path, current_list)
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing from list: {e}")
            return False
    
    def is_admin(self, user_id: str) -> bool:
        """Check if a user is an admin."""
        owner_id = self.get('access.owner_id')
        admin_ids = self.get('access.admin_ids', [])
        return user_id == owner_id or user_id in admin_ids
    
    def can_use_bot(self, user_id: str) -> bool:
        """Check if a user can use the bot"""
        # Check blacklist
        if str(user_id) in self.get('access.blacklisted_users', []):
            return False
        
        # Check whitelist if enabled
        whitelist_enabled = self.get('access.whitelist_enabled', False)
        if whitelist_enabled:
            return str(user_id) in self.get('access.whitelisted_users', [])
        
        return True
    
    def get_notification_channel(self, guild_id: str) -> Optional[str]:
        """Get the notification channel for a specific guild"""
        channels = self.get('channels.notifications', {})
        return channels.get(str(guild_id))
    
    def set_notification_channel(self, guild_id: str, channel_id: str) -> bool:
        """Set the notification channel for a specific guild"""
        try:
            channels = self.get('channels.notifications', {})
            channels[str(guild_id)] = channel_id
            return self.set('channels.notifications', channels)
        except Exception as e:
            logger.error(f"Error setting notification channel: {e}")
            return False
    
    def get_embed_color(self, type_: str) -> int:
        """Get embed color by type."""
        colors = {
            'success': 0x00ff00,  # Green
            'error': 0xff0000,    # Red
            'info': 0x0000ff,     # Blue
            'flip': 0xffa500      # Orange
        }
        return self.get(f'embeds.colors.{type_}', colors.get(type_, 0x000000))

    def get_flip_settings(self) -> Dict[str, Any]:
        """Get all flip detection settings"""
        return self.get('flip_settings', {})
    
    def update_flip_settings(self, settings: Dict[str, Any]) -> bool:
        """Update flip detection settings"""
        try:
            current_settings = self.get('flip_settings', {})
            current_settings.update(settings)
            return self.set('flip_settings', current_settings)
        except Exception as e:
            logger.error(f"Error updating flip settings: {e}")
            return False 

    def get_button_style(self, button_id: str) -> str:
        """Get button style configuration."""
        return self.get(f'buttons.{button_id}_style', 'blurple')

    def get_button_label(self, button_id: str) -> str:
        """Get button label configuration."""
        return self.get(f'buttons.{button_id}_label', button_id.title())

    def get_button_emoji(self, button_id: str) -> str:
        """Get button emoji configuration."""
        return self.get(f'buttons.{button_id}_emoji', '')

    def get_template(self, template_id: str) -> Optional[Dict]:
        """Get server template configuration."""
        return self.get(f'templates.{template_id}') 