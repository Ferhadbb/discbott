import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from typing import Optional
from datetime import datetime
from config_manager import ConfigManager
from auth_manager import AuthManager

logger = logging.getLogger('button_interactions')
config = ConfigManager()

class VerifyModal(discord.ui.Modal, title="Microsoft Account Verification"):
    nickname = discord.ui.TextInput(
        label="Nickname",
        placeholder="Enter your nickname",
        required=True,
        min_length=2,
        max_length=32
    )
    
    email = discord.ui.TextInput(
        label="Email Address",
        placeholder="Email linked to your Microsoft account",
        required=True,
        min_length=5,
        max_length=100
    )
    
    def __init__(self, auth_manager):
        super().__init__()
        self.auth_manager = auth_manager
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            success, message = await self.auth_manager.start_otp_verification(
                interaction.user,
                self.nickname.value,
                self.email.value
            )
            
            if success:
                embed = discord.Embed(
                    title="📧 Microsoft Account Verification",
                    description=message,
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ Verification Error",
                    description=message,
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in Microsoft verification: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class OTPVerifyModal(discord.ui.Modal, title="Enter Microsoft Code"):
    otp_code = discord.ui.TextInput(
        label="Verification Code",
        placeholder="Enter the code from your Microsoft email",
        required=True,
        min_length=6,
        max_length=8
    )
    
    def __init__(self, auth_manager):
        super().__init__()
        self.auth_manager = auth_manager
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            success, message = await self.auth_manager.verify_otp(
                interaction.user,
                self.otp_code.value
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Verification Successful",
                    description="Your Microsoft account has been verified! Welcome to the server!",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Verification Failed",
                    description=message,
                    color=discord.Color.red()
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in code verification: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class ButtonInteractions(commands.Cog, name="ButtonInteractions"):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = None
        logger.info("ButtonInteractions cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.auth_manager = self.bot.auth_manager
        logger.info("ButtonInteractions cog is ready")
        logger.info(f"Commands registered: {[cmd.name for cmd in self.bot.tree.get_commands()]}")
        
        # Check if our command is registered
        setup_welcome_exists = any(cmd.name == "setup_welcome" for cmd in self.bot.tree.get_commands())
        if not setup_welcome_exists:
            logger.warning("setup_welcome command not found in global commands, forcing sync")
            try:
                await self.bot.tree.sync()
                logger.info("Forced command sync complete")
            except Exception as e:
                logger.error(f"Error forcing command sync: {e}")
    
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
            await interaction.response.defer(ephemeral=True)
            target_channel = channel or interaction.channel
            embed_title = title or "🎮 Welcome to FlipperBot!"
            embed_description = description or (
                "Welcome to our server! To gain access to all channels, please verify yourself using one of the methods below.\n\n"
                "**🔐 OAuth Login**\n"
                "• Secure login with your Microsoft account\n"
                "• Quick and easy verification\n\n"
                "**📧 OTP Login**\n"
                "• One-time password sent to your email\n"
                "• Enter your nickname and email\n\n"
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
            view = discord.ui.View(timeout=None)
            oauth_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=config.get('buttons.verify_label', 'OAuth Login'),
                custom_id='oauth_button',
                emoji="🔐"
            )
            otp_button = discord.ui.Button(
                style=discord.ButtonStyle.blurple,
                label="OTP Login",
                custom_id='otp_button',
                emoji="📧"
            )
            enter_otp_button = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                label="Enter OTP",
                custom_id='enter_otp_button',
                emoji="✏️"
            )
            qa_button = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                label=config.get('buttons.qa_label', 'Q&A'),
                custom_id='qa_button',
                emoji="❓"
            )
            view.add_item(oauth_button)
            view.add_item(otp_button)
            view.add_item(enter_otp_button)
            view.add_item(qa_button)
            welcome_msg = await target_channel.send(embed=embed, view=view)
            success_embed = discord.Embed(
                title="✅ Welcome Embed Created",
                description=f"Welcome embed with verification buttons has been sent to {target_channel.mention}.",
                color=discord.Color.green()
            )
            try:
                await interaction.followup.send(embed=success_embed, ephemeral=True)
            except discord.errors.NotFound:
                logger.warning("Interaction expired before sending followup")
        except Exception as e:
            logger.error(f"Error creating welcome embed: {e}")
            try:
                await interaction.followup.send(f"Error creating welcome embed: {e}", ephemeral=True)
            except Exception as followup_error:
                logger.error(f"Could not send error message: {followup_error}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Get or create the FlipperBot channel
        flipper_channel = discord.utils.get(member.guild.channels, name="flipperbot")
        if not flipper_channel:
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            flipper_channel = await member.guild.create_text_channel('flipperbot', overwrites=overwrites)
        
        # Add unverified role
        unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
        if not unverified_role:
            unverified_role = await member.guild.create_role(
                name="❌ Unverified",
                color=discord.Color.red(),
                reason="Role for unverified members"
            )
        await member.add_roles(unverified_role)
        
        # Update channel permissions for the new member
        await flipper_channel.set_permissions(member, read_messages=True, send_messages=False)
        
        # Create welcome message with buttons
        embed = discord.Embed(
            title="🎮 Welcome to FlipperBot!",
            description=(
                "Welcome! Please choose a verification method:\n\n"
                "1️⃣ **OAuth Verification**\n"
                "• Secure login with Microsoft\n"
                "• Automatic verification\n\n"
                "2️⃣ **OTP Verification**\n"
                "• Enter your nickname and email\n"
                "• Receive OTP code\n"
                "• Enter the code to verify\n\n"
                "Choose your preferred method below:"
            ),
            color=discord.Color.blue()
        )
        
        view = discord.ui.View(timeout=None)
        
        # OAuth button
        oauth_button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="OAuth Login",
            custom_id='oauth_button',
            emoji="🔐"
        )
        
        # OTP button
        otp_button = discord.ui.Button(
            style=discord.ButtonStyle.blurple,
            label="OTP Login",
            custom_id='otp_button',
            emoji="📧"
        )
        
        # Enter OTP button
        enter_otp_button = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            label="Enter OTP",
            custom_id='enter_otp_button',
            emoji="✏️"
        )
        
        # Q&A button
        qa_button = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            label="Q&A",
            custom_id='qa_button',
            emoji="❓"
        )
        
        view.add_item(oauth_button)
        view.add_item(otp_button)
        view.add_item(enter_otp_button)
        view.add_item(qa_button)
        
        await flipper_channel.send(embed=embed, view=view)
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        if not hasattr(interaction, 'data') or not interaction.data or 'custom_id' not in interaction.data:
            # Silenced noisy warning
            return
        custom_id = interaction.data['custom_id']
        if custom_id == 'oauth_button':
            await self.handle_oauth(interaction)
        elif custom_id == 'otp_button':
            await self.handle_otp_start(interaction)
        elif custom_id == 'enter_otp_button':
            await self.handle_otp_enter(interaction)
        elif custom_id == 'qa_button':
            await self.handle_qa(interaction)
        else:
            logger.info(f"Received interaction with unknown custom_id: {custom_id}")
    
    async def handle_oauth(self, interaction: discord.Interaction):
        try:
            auth_manager = getattr(self.bot, 'auth_manager', None)
            if not auth_manager:
                raise RuntimeError("Auth manager is not initialized.")
            auth_url, session_id = auth_manager.generate_auth_url()
            embed = discord.Embed(
                title="🔐 Microsoft Account Verification",
                description=(
                    "Please follow these steps:\n\n"
                    "1️⃣ **Click the Link Below**\n"
                    f"• [Click here to verify with Microsoft]({auth_url})\n\n"
                    "2️⃣ **Login Process**\n"
                    "• Sign in with your Microsoft account\n"
                    "• Complete the verification\n\n"
                    "3️⃣ **Completion**\n"
                    "• You'll be redirected back\n"
                    "• Your roles will be updated automatically\n\n"
                    "⚠️ This link expires in 10 minutes"
                ),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in OAuth process: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    async def handle_otp_start(self, interaction: discord.Interaction):
        try:
            auth_manager = getattr(self.bot, 'auth_manager', None)
            if not auth_manager:
                raise RuntimeError("Auth manager is not initialized.")
            modal = VerifyModal(auth_manager)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"Error in Microsoft verification: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    async def handle_otp_enter(self, interaction: discord.Interaction):
        try:
            auth_manager = getattr(self.bot, 'auth_manager', None)
            if not auth_manager:
                raise RuntimeError("Auth manager is not initialized.")
            modal = OTPVerifyModal(auth_manager)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"Error in OTP entry: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="An error occurred. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    async def handle_qa(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="❓ Frequently Asked Questions",
            description="Here are some common questions about verification:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="What verification method should I choose?",
            value=(
                "**OAuth (Recommended)**\n"
                "• Direct Microsoft account login\n"
                "• Fastest verification method\n"
                "• Most secure option\n\n"
                "**Microsoft Account OTP**\n"
                "• Uses any email linked to your Microsoft account\n"
                "• Verification code sent to your email\n"
                "• Requires Microsoft account"
            ),
            inline=False
        )
        
        embed.add_field(
            name="How does OAuth work?",
            value=(
                "1. Click the OAuth Login button\n"
                "2. Sign in with your Microsoft account\n"
                "3. Authorize the application\n"
                "4. You'll be automatically verified"
            ),
            inline=False
        )
        
        embed.add_field(
            name="How does Email OTP work?",
            value=(
                "1. Click Email OTP Login\n"
                "2. Enter your email (any email linked to Microsoft account)\n"
                "3. Check your email for the verification code\n"
                "4. Enter the code to verify"
            ),
            inline=False
        )
        
        embed.add_field(
            name="What emails can I use?",
            value=(
                "You can use ANY email that's linked to your Microsoft account:\n"
                "• Your primary Microsoft account email\n"
                "• Any alias emails you've added\n"
                "• Work/school emails connected to Microsoft\n"
                "• Any email you use to sign in to Microsoft services"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Need More Help?",
            value="Contact our support team or ask in the help channel!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ButtonInteractions(bot)) 