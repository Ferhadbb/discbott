import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Dict
from datetime import datetime
from config_manager import ConfigManager
import json
import logging
import asyncio

logger = logging.getLogger('server_templates')
config = ConfigManager()

class ServerTemplates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Base roles that are common across all templates
        self.base_roles = {
            "Owner": {
                "color": 0xFF0000,  # Red
                "permissions": discord.Permissions(administrator=True),
                "position": 10,
                "emoji": "👑",
                "hoisted": True
            },
            "Admin": {
                "color": 0xFF4500,  # Orange Red
                "permissions": discord.Permissions(
                    manage_guild=True,
                    manage_roles=True,
                    manage_channels=True,
                    manage_messages=True,
                    kick_members=True,
                    ban_members=True,
                    view_audit_log=True
                ),
                "position": 9,
                "emoji": "⚡",
                "hoisted": True
            },
            "Support": {
                "color": 0x4169E1,  # Royal Blue
                "permissions": discord.Permissions(
                    manage_messages=True,
                    kick_members=True,
                    view_audit_log=True
                ),
                "position": 8,
                "emoji": "🛠️",
                "hoisted": True
            },
            "Media": {
                "color": 0x9932CC,  # Dark Orchid
                "permissions": discord.Permissions(
                    manage_messages=True,
                    embed_links=True,
                    attach_files=True,
                    mention_everyone=True
                ),
                "position": 7,
                "emoji": "📸",
                "hoisted": True
            },
            "Supreme Member": {
                "color": 0xFFD700,  # Gold
                "permissions": discord.Permissions(
                    create_instant_invite=True,
                    change_nickname=True,
                    add_reactions=True,
                    external_emojis=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                    connect=True,
                    speak=True,
                    stream=True
                ),
                "position": 6,
                "emoji": "⭐",
                "hoisted": True
            },
            "OG Member": {
                "color": 0xC0C0C0,  # Silver
                "permissions": discord.Permissions(
                    create_instant_invite=True,
                    change_nickname=True,
                    add_reactions=True,
                    external_emojis=True,
                    read_message_history=True,
                    connect=True,
                    speak=True
                ),
                "position": 5,
                "emoji": "🌟",
                "hoisted": True
            },
            "Member": {
                "color": 0x32CD32,  # Lime Green
                "permissions": discord.Permissions(
                    create_instant_invite=True,
                    change_nickname=True,
                    add_reactions=True,
                    read_message_history=True,
                    connect=True,
                    speak=True
                ),
                "position": 4,
                "emoji": "🎮",
                "hoisted": True
            },
            "Verified": {
                "color": 0x98FB98,  # Pale Green
                "permissions": discord.Permissions(
                    read_messages=True,
                    send_messages=True,
                    read_message_history=True,
                    connect=True
                ),
                "position": 3,
                "emoji": "✅",
                "hoisted": False
            },
            "Unverified": {
                "color": 0x808080,  # Gray
                "permissions": discord.Permissions(
                    read_messages=False,
                    send_messages=False
                ),
                "position": 1,
                "emoji": "❌",
                "hoisted": False
            }
        }

        # Template-specific roles
        self.template_roles = {
            "dungeon": {
                "Carrier": {
                    "color": 0xE6BE8A,  # Gold-like
                    "permissions": discord.Permissions(
                        create_instant_invite=True,
                        change_nickname=True,
                        add_reactions=True,
                        external_emojis=True,
                        read_message_history=True,
                        connect=True,
                        speak=True,
                        stream=True,
                        mention_everyone=True
                    ),
                    "position": 7,
                    "emoji": "⚔️",
                    "hoisted": True
                },
                "Dungeon Master": {
                    "color": 0x800080,  # Purple
                    "permissions": discord.Permissions(
                        create_instant_invite=True,
                        change_nickname=True,
                        add_reactions=True,
                        external_emojis=True,
                        read_message_history=True,
                        connect=True,
                        speak=True,
                        stream=True
                    ),
                    "position": 6,
                    "emoji": "🏰",
                    "hoisted": True
                }
            },
            "farming": {
                "Garden Builder": {
                    "color": 0x90EE90,  # Light Green
                    "permissions": discord.Permissions(
                        create_instant_invite=True,
                        change_nickname=True,
                        add_reactions=True,
                        external_emojis=True,
                        read_message_history=True,
                        connect=True,
                        speak=True,
                        stream=True,
                        mention_everyone=True
                    ),
                    "position": 7,
                    "emoji": "🌾",
                    "hoisted": True
                },
                "Master Farmer": {
                    "color": 0x228B22,  # Forest Green
                    "permissions": discord.Permissions(
                        create_instant_invite=True,
                        change_nickname=True,
                        add_reactions=True,
                        external_emojis=True,
                        read_message_history=True,
                        connect=True,
                        speak=True,
                        stream=True
                    ),
                    "position": 6,
                    "emoji": "🌱",
                    "hoisted": True
                }
            },
            "general": {
                "Event Manager": {
                    "color": 0xFF69B4,  # Hot Pink
                    "permissions": discord.Permissions(
                        create_instant_invite=True,
                        change_nickname=True,
                        add_reactions=True,
                        external_emojis=True,
                        read_message_history=True,
                        connect=True,
                        speak=True,
                        stream=True,
                        mention_everyone=True
                    ),
                    "position": 7,
                    "emoji": "🎉",
                    "hoisted": True
                },
                "Community Leader": {
                    "color": 0x40E0D0,  # Turquoise
                    "permissions": discord.Permissions(
                        create_instant_invite=True,
                        change_nickname=True,
                        add_reactions=True,
                        external_emojis=True,
                        read_message_history=True,
                        connect=True,
                        speak=True,
                        stream=True
                    ),
                    "position": 6,
                    "emoji": "🌟",
                    "hoisted": True
                }
            }
        }

        self.templates = {
            "dungeon": {
                "name": "🏰 Dungeon Server",
                "categories": {
                    "📢 MAIN": [
                        ("📣-announcements", True),
                        ("📝-updates", False),
                        ("🎉-giveaways", False)
                    ],
                    "💬 COMMUNITY": [
                        ("👋-welcome", False),
                        ("💭-general", False),
                        ("😂-memes", False),
                        ("🎨-media", False)
                    ],
                    "🏰 DUNGEONS": [
                        ("⚔️-carry-services", False),
                        ("🎯-lfg-catacombs", False),
                        ("📊-dungeon-stats", False),
                        ("💡-dungeon-tips", False),
                        ("💰-prices", False)
                    ],
                    "🎮 GAMING": [
                        ("🎯-party-finder", False),
                        ("📈-progress", False),
                        ("🏆-achievements", False)
                    ],
                    "🤖 BOT": [
                        ("🤖-commands", False),
                        ("📊-stats", False),
                        ("💡-suggestions", False)
                    ]
                }
            },
            "farming": {
                "name": "🌾 Farming Server",
                "categories": {
                    "📢 MAIN": [
                        ("📣-announcements", True),
                        ("📝-updates", False),
                        ("🎉-giveaways", False)
                    ],
                    "💬 COMMUNITY": [
                        ("👋-welcome", False),
                        ("💭-general", False),
                        ("😂-memes", False),
                        ("🎨-media", False)
                    ],
                    "🌾 FARMING": [
                        ("🌱-garden-services", False),
                        ("📊-farming-stats", False),
                        ("💰-profit-calc", False),
                        ("💡-farming-tips", False),
                        ("🌿-garden-showcase", False)
                    ],
                    "🏆 COMPETITIONS": [
                        ("🏃-farming-events", False),
                        ("📈-leaderboards", False),
                        ("🎁-rewards", False)
                    ],
                    "🤖 BOT": [
                        ("🤖-commands", False),
                        ("📊-stats", False),
                        ("💡-suggestions", False)
                    ]
                }
            },
            "general": {
                "name": "🌟 General Gaming Server",
                "categories": {
                    "📢 MAIN": [
                        ("📣-announcements", True),
                        ("📝-updates", False),
                        ("🎉-giveaways", False)
                    ],
                    "💬 COMMUNITY": [
                        ("👋-welcome", False),
                        ("💭-general", False),
                        ("😂-memes", False),
                        ("🎨-media", False),
                        ("🎵-music", False)
                    ],
                    "🎮 GAMING": [
                        ("🎯-lfg", False),
                        ("💬-game-chat", False),
                        ("🏆-achievements", False),
                        ("📈-stats", False)
                    ],
                    "🎉 EVENTS": [
                        ("📅-event-schedule", False),
                        ("🎪-event-chat", False),
                        ("🏆-winners", False)
                    ],
                    "🤖 BOT": [
                        ("🤖-commands", False),
                        ("📊-stats", False),
                        ("💡-suggestions", False)
                    ]
                }
            }
        }

    @app_commands.command(name="template_use", description="Apply a server template")
    @app_commands.choices(template=[
        app_commands.Choice(name="🏰 Dungeon Server", value="dungeon"),
        app_commands.Choice(name="🌾 Farming Server", value="farming"),
        app_commands.Choice(name="🌟 General Gaming Server", value="general")
    ])
    async def template_use(self, interaction: discord.Interaction, template: str):
        if not interaction.user.guild_permissions.manage_guild:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You need 'Manage Server' permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Try to defer, but handle the case where the interaction might have timed out
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            # Interaction already timed out, we can't respond to it
            logger.error("Interaction timed out before we could defer it")
            return

        template_data = self.templates.get(template)
        if not template_data:
            await interaction.followup.send("Invalid template selected.", ephemeral=True)
            return

        progress_embed = discord.Embed(
            title=f"🔨 Setting up {template_data['name']}",
            description="Creating roles and channels...",
            color=discord.Color.blue()
        )
        progress_msg = await interaction.followup.send(embed=progress_embed)

        try:
            # Create base roles
            for role_name, role_data in self.base_roles.items():
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if not role:
                    await interaction.guild.create_role(
                        name=f"{role_data['emoji']} {role_name}",
                        color=discord.Color(role_data['color']),
                        permissions=role_data['permissions'],
                        hoist=role_data['hoisted'],
                        reason=f"Part of {template_data['name']} template"
                    )
                    logger.info(f"Created role: {role_name}")

            # Create template-specific roles
            template_specific_roles = self.template_roles.get(template, {})
            for role_name, role_data in template_specific_roles.items():
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if not role:
                    await interaction.guild.create_role(
                        name=f"{role_data['emoji']} {role_name}",
                        color=discord.Color(role_data['color']),
                        permissions=role_data['permissions'],
                        hoist=role_data['hoisted'],
                        reason=f"Part of {template_data['name']} template"
                    )
                    logger.info(f"Created template-specific role: {role_name}")

            # Create categories and channels
            for category_name, channels in template_data["categories"].items():
                # Add a small delay to avoid rate limits
                await asyncio.sleep(0.5)
                
                category = await interaction.guild.create_category(
                    name=category_name,
                    position=len(interaction.guild.categories)
                )

                # Set up category permissions
                await category.set_permissions(
                    interaction.guild.default_role,
                    read_messages=False,
                    send_messages=False
                )
                
                verified_role = discord.utils.get(interaction.guild.roles, name="✅ Verified")
                if verified_role:
                    await category.set_permissions(
                        verified_role,
                        read_messages=True,
                        send_messages=True
                    )

                # Create channels in category
                for channel_name, is_news in channels:
                    # Add a small delay to avoid rate limits
                    await asyncio.sleep(0.3)
                    
                    # Create a regular text channel first
                    channel = await interaction.guild.create_text_channel(
                        name=channel_name,
                        category=category
                    )
                    
                    # If it should be a news channel, convert it
                    if is_news:
                        try:
                            # Use the proper enum value for announcement channels
                            await channel.edit(type=discord.ChannelType.news)
                            logger.info(f"Created announcement channel: {channel_name}")
                        except discord.errors.HTTPException as e:
                            logger.error(f"Could not convert {channel_name} to announcement channel: {e}")
                            # Continue anyway with a regular text channel
                        except Exception as e:
                            logger.error(f"Unexpected error converting {channel_name} to announcement channel: {e}")
                            # Continue anyway with a regular text channel

                    # Set specific permissions for announcement channels
                    if is_news:
                        await channel.set_permissions(interaction.guild.default_role, send_messages=False)
                        admin_role = discord.utils.get(interaction.guild.roles, name="⚡ Admin")
                        if admin_role:
                            await channel.set_permissions(admin_role, send_messages=True)

            success_embed = discord.Embed(
                title=f"✅ {template_data['name']} Setup Complete!",
                description=(
                    "Server has been set up successfully!\n\n"
                    "**Created Items:**\n"
                    "• All necessary roles with permissions\n"
                    "• Organized categories and channels\n"
                    "• Proper permission setup\n\n"
                    "**Next Steps:**\n"
                    "1. Assign Owner and Admin roles\n"
                    "2. Review channel permissions\n"
                    "3. Customize role colors if desired"
                ),
                color=discord.Color.green()
            )
            await progress_msg.edit(embed=success_embed)

        except discord.Forbidden:
            error_embed = discord.Embed(
                title="❌ Setup Failed",
                description="I don't have permission to create roles or channels.",
                color=discord.Color.red()
            )
            await progress_msg.edit(embed=error_embed)
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Setup Failed",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await progress_msg.edit(embed=error_embed)

async def setup(bot):
    await bot.add_cog(ServerTemplates(bot)) 