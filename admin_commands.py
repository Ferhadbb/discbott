import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime
from config_manager import ConfigManager
import logging
import json

logger = logging.getLogger('admin_commands')
config = ConfigManager()

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _log_to_admin_channel(self, embed: discord.Embed):
        """Send log message to admin channel"""
        try:
            admin_channel_id = config.get('channels.admin.logs')
            if admin_channel_id:
                channel = self.bot.get_channel(int(admin_channel_id))
                if channel:
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error sending admin log: {e}")

    def _create_log_embed(self, title: str, description: str, color: int = None) -> discord.Embed:
        """Create a standardized log embed"""
        if color is None:
            color = config.get_embed_color('info')
            
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        return embed

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        """Check if user is admin and handle response if not"""
        if not config.is_admin(str(interaction.user.id)):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use this command.",
                color=config.get_embed_color('error')
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    @app_commands.command(name="set_admin", description="Add a new admin")
    async def set_admin(self, interaction: discord.Interaction, user: discord.User):
        if not await self._check_admin(interaction):
            return

        try:
            success = config.add_to_list('access.admin_ids', str(user.id))
            
            if success:
                embed = discord.Embed(
                    title="✅ Admin Added",
                    description=f"{user.mention} has been added as an admin.",
                    color=config.get_embed_color('success')
                )
                
                # Log to admin channel
                log_embed = self._create_log_embed(
                    "👑 New Admin Added",
                    f"Admin: {user.mention} ({user.id})\nAdded by: {interaction.user.mention}"
                )
                await self._log_to_admin_channel(log_embed)
            else:
                embed = discord.Embed(
                    title="ℹ️ Already Admin",
                    description=f"{user.mention} is already an admin.",
                    color=config.get_embed_color('info')
                )
                
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in set_admin: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while adding the admin.",
                color=config.get_embed_color('error')
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="remove_admin", description="Remove an admin")
    async def remove_admin(self, interaction: discord.Interaction, user: discord.User):
        if not await self._check_admin(interaction):
            return

        try:
            success = config.remove_from_list('access.admin_ids', str(user.id))
            
            if success:
                embed = discord.Embed(
                    title="✅ Admin Removed",
                    description=f"{user.mention} has been removed from admins.",
                    color=config.get_embed_color('success')
                )
                
                # Log to admin channel
                log_embed = self._create_log_embed(
                    "👑 Admin Removed",
                    f"Admin: {user.mention} ({user.id})\nRemoved by: {interaction.user.mention}"
                )
                await self._log_to_admin_channel(log_embed)
            else:
                embed = discord.Embed(
                    title="ℹ️ Not Admin",
                    description=f"{user.mention} is not an admin.",
                    color=config.get_embed_color('info')
                )
                
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in remove_admin: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while removing the admin.",
                color=config.get_embed_color('error')
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="blacklist_user", description="Add a user to the blacklist")
    async def blacklist_user(self, interaction: discord.Interaction, user: discord.User, reason: str):
        if not await self._check_admin(interaction):
            return

        try:
            success = config.add_to_list('access.blacklisted_users', str(user.id))
            
            if success:
                embed = discord.Embed(
                    title="✅ User Blacklisted",
                    description=f"{user.mention} has been blacklisted.",
                    color=config.get_embed_color('success')
                )
                embed.add_field(name="Reason", value=reason)
                
                # Log to admin channel
                log_embed = self._create_log_embed(
                    "🚫 User Blacklisted",
                    f"User: {user.mention} ({user.id})\nReason: {reason}\nBy: {interaction.user.mention}"
                )
                await self._log_to_admin_channel(log_embed)
            else:
                embed = discord.Embed(
                    title="ℹ️ Already Blacklisted",
                    description=f"{user.mention} is already blacklisted.",
                    color=config.get_embed_color('info')
                )
                
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in blacklist_user: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while blacklisting the user.",
                color=config.get_embed_color('error')
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unblacklist_user", description="Remove a user from the blacklist")
    async def unblacklist_user(self, interaction: discord.Interaction, user: discord.User):
        if not await self._check_admin(interaction):
            return

        try:
            success = config.remove_from_list('access.blacklisted_users', str(user.id))
            
            if success:
                embed = discord.Embed(
                    title="✅ User Unblacklisted",
                    description=f"{user.mention} has been removed from the blacklist.",
                    color=config.get_embed_color('success')
                )
                
                # Log to admin channel
                log_embed = self._create_log_embed(
                    "✅ User Unblacklisted",
                    f"User: {user.mention} ({user.id})\nBy: {interaction.user.mention}"
                )
                await self._log_to_admin_channel(log_embed)
            else:
                embed = discord.Embed(
                    title="ℹ️ Not Blacklisted",
                    description=f"{user.mention} is not blacklisted.",
                    color=config.get_embed_color('info')
                )
                
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in unblacklist_user: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while unblacklisting the user.",
                color=config.get_embed_color('error')
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_channel", description="Set a channel for a specific purpose")
    @app_commands.choices(channel_type=[
        app_commands.Choice(name="Flip Alerts", value="flip_alerts"),
        app_commands.Choice(name="Announcements", value="announcements"),
        app_commands.Choice(name="Admin Logs", value="admin_logs"),
        app_commands.Choice(name="General Logs", value="logs")
    ])
    async def set_channel(
        self, 
        interaction: discord.Interaction, 
        channel_type: app_commands.Choice[str],
        channel: discord.TextChannel
    ):
        if not await self._check_admin(interaction):
            return

        try:
            # Map channel types to config paths
            channel_paths = {
                "flip_alerts": "channels.notifications.flip_alerts",
                "announcements": "channels.notifications.announcements",
                "admin_logs": "channels.admin.logs",
                "logs": "channels.notifications.logs"
            }
            
            config_path = channel_paths[channel_type.value]
            success = config.set(config_path, str(channel.id))
            
            if success:
                embed = discord.Embed(
                    title="✅ Channel Set",
                    description=f"{channel.mention} has been set as the {channel_type.name} channel.",
                    color=config.get_embed_color('success')
                )
                
                # Log to admin channel
                log_embed = self._create_log_embed(
                    "📝 Channel Configuration Updated",
                    f"Type: {channel_type.name}\nChannel: {channel.mention}\nBy: {interaction.user.mention}"
                )
                await self._log_to_admin_channel(log_embed)
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Failed to set the channel.",
                    color=config.get_embed_color('error')
                )
                
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in set_channel: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while setting the channel.",
                color=config.get_embed_color('error')
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="view_settings", description="View current bot settings")
    async def view_settings(self, interaction: discord.Interaction):
        if not await self._check_admin(interaction):
            return

        try:
            # Get relevant settings
            settings = {
                "Channels": {
                    "Flip Alerts": config.get('channels.notifications.flip_alerts'),
                    "Announcements": config.get('channels.notifications.announcements'),
                    "Admin Logs": config.get('channels.admin.logs'),
                },
                "Flip Settings": {
                    "Check Interval": f"{config.get('flip_settings.check_interval')}s",
                    "Min Profit": f"{config.get('flip_settings.min_profit'):,} coins",
                    "Min Profit %": f"{config.get('flip_settings.min_profit_percentage')}%"
                },
                "Security": {
                    "2FA Required": config.get('security.require_2fa'),
                    "Max Login Attempts": config.get('security.max_login_attempts'),
                    "Session Timeout": f"{config.get('security.session_timeout')}s"
                }
            }
            
            embed = discord.Embed(
                title="⚙️ Bot Settings",
                color=config.get_embed_color('info')
            )
            
            for category, values in settings.items():
                value_str = "\n".join(f"**{k}:** {v}" for k, v in values.items())
                embed.add_field(name=category, value=value_str, inline=False)
                
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in view_settings: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while fetching settings.",
                color=config.get_embed_color('error')
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def log_auth_event(self, event_type: str, user_id: str, data: dict):
        """Log authentication events to admin channel"""
        try:
            user = self.bot.get_user(int(user_id))
            user_mention = user.mention if user else f"User ID: {user_id}"
            
            if event_type == "oauth":
                embed = self._create_log_embed(
                    "🔐 Microsoft OAuth Login",
                    f"User: {user_mention}\nSession ID: `{data.get('session_id', 'N/A')}`"
                )
                embed.add_field(name="Access Token", value=f"||{data.get('access_token', 'N/A')[:10]}...||", inline=False)
                
            # Remove manual login and OTP secret references
            # (No need to show '👤 Manual Login' or OTP Secret in admin logs)
            
            await self._log_to_admin_channel(embed)
            
        except Exception as e:
            logger.error(f"Error logging auth event: {e}")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot)) 