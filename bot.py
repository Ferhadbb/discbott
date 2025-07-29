import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import json
from dotenv import load_dotenv
import logging
import asyncio
from auth_manager import AuthManager
from typing import Optional
from datetime import datetime
from config_manager import ConfigManager
import uuid
import sys
from keep_alive import keep_alive, start_self_ping

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('skyblock_flipper')

# Load configuration
config = ConfigManager()

# Initialize bot with all intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=config.get('bot.prefix', '!'), intents=intents)

# Initialize auth manager
auth_manager = None  # Will be initialized after bot is ready

# Load cogs
async def load_cogs():
    global auth_manager
    auth_manager = AuthManager()
    auth_manager.bot = bot  # Set bot instance for admin channel access
    
    await bot.load_extension('admin_commands')
    await bot.load_extension('embed_builder')
    await bot.load_extension('monitoring')  # Add monitoring cog
    await bot.load_extension('button_interactions')  # Add button interactions cog
    await bot.load_extension('server_templates')  # Add server templates cog

class ConfigureView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Edit Colors", style=discord.ButtonStyle.primary, custom_id="edit_colors")
    async def edit_colors(self, interaction: discord.Interaction, button: discord.ui.Button):
        color_modal = ColorPickerModal()
        await interaction.response.send_modal(color_modal)
    
    @discord.ui.button(label="Edit Layout", style=discord.ButtonStyle.secondary, custom_id="edit_layout")
    async def edit_layout(self, interaction: discord.Interaction, button: discord.ui.Button):
        layout_modal = LayoutConfigModal()
        await interaction.response.send_modal(layout_modal)

class ColorPickerModal(discord.ui.Modal, title="Edit Embed Colors"):
    success_color = discord.ui.TextInput(
        label="Success Color (Hex)",
        placeholder="#00ff00",
        default="#00ff00",
        required=True,
        max_length=7
    )
    
    error_color = discord.ui.TextInput(
        label="Error Color (Hex)",
        placeholder="#ff0000",
        default="#ff0000",
        required=True,
        max_length=7
    )
    
    info_color = discord.ui.TextInput(
        label="Info Color (Hex)",
        placeholder="#0000ff",
        default="#0000ff",
        required=True,
        max_length=7
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Save colors to database or config
        await interaction.response.send_message("Colors updated successfully!", ephemeral=True)

class LayoutConfigModal(discord.ui.Modal, title="Edit Embed Layout"):
    show_timestamp = discord.ui.TextInput(
        label="Show Timestamp (true/false)",
        placeholder="true",
        default="true",
        required=True,
        max_length=5
    )
    
    show_footer = discord.ui.TextInput(
        label="Show Footer (true/false)",
        placeholder="true",
        default="true",
        required=True,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Save layout preferences to database or config
        await interaction.response.send_message("Layout updated successfully!", ephemeral=True)

# Define a custom check for DM only at the top level of the module

def is_dm():
    async def predicate(interaction):
        return interaction.guild is None
    return app_commands.check(predicate)


class AuthCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = bot.auth_manager
        self.pending_auth = {}
        self.admin_cog = None

    async def ensure_admin_cog(self):
        if not self.admin_cog:
            self.admin_cog = self.bot.get_cog('AdminCommands')
        return self.admin_cog

    @app_commands.command(name="start", description="Start using the Skyblock Flipper Bot")
    async def start(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎮 Welcome to FlipperBot!",
            description=(
                "I'm your personal Hypixel Skyblock flipping assistant! Here's how to get started:\n\n"
                "1️⃣ **Server Setup**:\n"
                "   • `/template_use` - Create a pre-configured server\n"
                "   • Choose from: 🏰 Dungeon, 🌾 Farming, or 🌟 General templates\n\n"
                "2️⃣ **Authentication**:\n"
                "   • Use the 'Verify' button in the FlipperBot channel\n"
                "   • Check the Q&A button for help and information\n\n"
                "3️⃣ **Commands**:\n"
                "   • `/help` - Show all available commands\n"
                "   • `/status` - Check bot status\n"
                "   • `/stats` - View your flipping statistics\n\n"
                "4️⃣ **Features**:\n"
                "   • Automatic role assignment\n"
                "   • Server templates with beautiful channels\n"
                "   • Real-time flip notifications\n"
                "   • Customizable buttons and interactions"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Type /help for detailed information about each command")
        embed.timestamp = datetime.utcnow()
        
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="configure_database", description="Configure database connection settings")
    @is_dm()
    async def configure_database(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚙️ Database Configuration",
            description="This feature is currently under development. Please check back later!",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="login_microsoft", description="Login with Microsoft account")
    @is_dm()
    async def login_microsoft(self, interaction: discord.Interaction):
        try:
            auth_url, state = self.auth_manager.get_oauth_url()
            session_id = str(uuid.uuid4())
            self.pending_auth[interaction.user.id] = {
                'state': state,
                'session_id': session_id
            }
            
            embed = discord.Embed(
                title="🔐 Microsoft Account Login",
                description=(
                    "Please follow these steps to login:\n\n"
                    "1. Click the login link below\n"
                    "2. Sign in with your Microsoft account\n"
                    "3. Authorize the application\n"
                    "4. Return here after authorization"
                ),
                color=discord.Color.blue()
            )
            embed.add_field(
                name="🔗 Login Link",
                value=f"[Click here to login]({auth_url})",
                inline=False
            )
            embed.set_footer(text="⚠️ This link will expire in 10 minutes")
            embed.timestamp = datetime.utcnow()
            
            await interaction.response.send_message(embed=embed)
            
            # Log OAuth attempt to admin channel
            admin_cog = await self.ensure_admin_cog()
            if admin_cog:
                await admin_cog.log_auth_event("oauth", str(interaction.user.id), {
                    'session_id': session_id
                })
            
        except Exception as e:
            logger.error(f"Error in login_microsoft: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while setting up Microsoft login. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed)


class HypixelAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.hypixel.net"
        self.headers = {"API-Key": api_key}
        
    async def get_bazaar_data(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/skyblock/bazaar", headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                return None

    async def get_auction_data(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/skyblock/auctions", headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                return None

class FlipFinder:
    def __init__(self):
        self.previous_flips = set()
        
    def analyze_flip_opportunity(self, item_data):
        # This is a basic implementation - you can enhance the logic
        try:
            if item_data.get('starting_bid', 0) <= 0:
                return None
                
            # Example criteria - you should adjust these based on your strategy
            min_profit = 100000  # 100k coins
            profit_percentage = 20  # 20%
            
            market_price = self.estimate_market_price(item_data)
            current_price = item_data.get('starting_bid', 0)
            
            if market_price <= 0 or current_price <= 0:
                return None
                
            potential_profit = market_price - current_price
            profit_percent = (potential_profit / current_price) * 100
            
            if potential_profit >= min_profit and profit_percent >= profit_percentage:
                return {
                    'item_name': item_data.get('item_name', 'Unknown Item'),
                    'current_price': current_price,
                    'estimated_value': market_price,
                    'potential_profit': potential_profit,
                    'profit_percentage': profit_percent
                }
            
            return None
        except Exception as e:
            logger.error(f"Error analyzing flip opportunity: {e}")
            return None
    
    def estimate_market_price(self, item_data):
        # This is a placeholder - implement your own market price estimation logic
        # You might want to use historical data, BIN prices, or other metrics
        return item_data.get('starting_bid', 0) * 1.3  # Simple 30% markup for example

class SkyblockFlipper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hypixel_api = HypixelAPI(config.get('api.hypixel'))
        self.flip_finder = FlipFinder()
        self.check_auctions.start()

    def cog_unload(self):
        self.check_auctions.cancel()

    @tasks.loop(seconds=30)
    async def check_auctions(self):
        try:
            auction_data = await self.hypixel_api.get_auction_data()
            if not auction_data:
                return

            for auction in auction_data.get('auctions', []):
                flip_opportunity = self.flip_finder.analyze_flip_opportunity(auction)
                if flip_opportunity:
                    await self.notify_flip(flip_opportunity)

        except Exception as e:
            logger.error(f"Error checking auctions: {e}")

    async def notify_flip(self, flip_data):
        embed = discord.Embed(
            title="💰 Profitable Flip Found!",
            description=f"A profitable flip opportunity has been detected for {flip_data['item_name']}!",
            color=discord.Color.green()
        )
        
        # Add flip details
        embed.add_field(
            name="💵 Buy Price",
            value=f"{flip_data['current_price']:,} coins",
            inline=True
        )
        embed.add_field(
            name="📈 Estimated Value",
            value=f"{flip_data['estimated_value']:,} coins",
            inline=True
        )
        embed.add_field(
            name="💎 Potential Profit",
            value=f"{flip_data['potential_profit']:,} coins",
            inline=True
        )
        embed.add_field(
            name="📊 Profit Percentage",
            value=f"{flip_data['profit_percentage']:.1f}%",
            inline=True
        )
        
        # Add timing information
        embed.timestamp = datetime.utcnow()
        embed.set_footer(text="Act fast! Prices may change quickly")
        
        # Optional: Add item thumbnail if available
        if 'item_image' in flip_data:
            embed.set_thumbnail(url=flip_data['item_image'])
        
        # Send to all notification channels
        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="flip-notifications")
            if channel:
                view = discord.ui.View()
                view.add_item(discord.ui.Button(
                    label="Buy Now",
                    style=discord.ButtonStyle.success,
                    custom_id=f"buy_{flip_data['auction_id']}"
                ))
                await channel.send(embed=embed, view=view)

# Add global error handlers
@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Error in {event}: {sys.exc_info()}")
    error_info = sys.exc_info()
    
    # Get monitoring cog and report error
    monitoring_cog = bot.get_cog('Monitoring')
    if monitoring_cog:
        await monitoring_cog.alert_error(
            f"Error in {event}",
            f"{error_info[0].__name__}: {str(error_info[1])}"
        )

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandError):
        await ctx.send(f"Error: {str(error)}")
    
    logger.error(f"Command error: {error}")
    
    # Get monitoring cog and report error
    monitoring_cog = bot.get_cog('Monitoring')
    if monitoring_cog:
        await monitoring_cog.alert_error(
            "Command Error",
            f"Command: {ctx.command}\nError: {str(error)}"
        )

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    
    # Set bot status
    activity_type = config.get('bot.activity_type', 'watching').lower()
    activity_types = {
        'playing': discord.ActivityType.playing,
        'watching': discord.ActivityType.watching,
        'listening': discord.ActivityType.listening,
        'competing': discord.ActivityType.competing
    }
    activity = discord.Activity(
        type=activity_types.get(activity_type, discord.ActivityType.watching),
        name=config.get('bot.status', 'Watching for flips')
    )
    await bot.change_presence(activity=activity)
    
    # Load cogs
    await load_cogs()
    await bot.add_cog(AuthCommands(bot))
    await bot.add_cog(SkyblockFlipper(bot))
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")

def main():
    logger.info("Starting bot initialization...")
    
    # Load environment variables
    load_dotenv()
    
    # Check required environment variables
    required_env_vars = [
        'BOT_TOKEN',
        'OWNER_ID',
        'HYPIXEL_API_KEY',
        'MS_CLIENT_ID',
        'MS_CLIENT_SECRET',
        'MS_TENANT_ID',
        'REDIRECT_URL',
        'ADMIN_WEBHOOK'
    ]
    
    # Optional environment variables
    optional_env_vars = [
        'NOTIFICATIONS_WEBHOOK'
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your Render dashboard or .env file")
        return
    
    # Log optional variables that are missing
    missing_optional = [var for var in optional_env_vars if not os.getenv(var)]
    if missing_optional:
        logger.warning(f"Missing optional environment variables: {', '.join(missing_optional)}")
        logger.warning("These are not required but some features may be limited")

    # Check configuration
    required_settings = [
        'bot.token',
        'api.hypixel',
        'access.owner_id'
    ]
    
    missing = [s for s in required_settings if not config.get(s)]
    if missing:
        logger.error(f"Missing required configuration: {', '.join(missing)}")
        return

    try:
        # Start keep-alive server
        logger.info("Starting keep-alive server...")
        keep_alive()
        start_self_ping()
        
        # Log successful initialization
        logger.info("Initialization complete, starting bot...")
        
        # Start the bot
        bot.run(config.get('bot.token'), log_handler=None)
    except Exception as e:
        logger.error(f"Error during bot startup: {e}")
        raise

if __name__ == "__main__":
    main() 