import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime
from config_manager import ConfigManager
from auth_manager import AuthManager
import logging

logger = logging.getLogger('button_interactions')
config = ConfigManager()

class ButtonInteractions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = AuthManager()
        
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
        
        # Add non-verified role
        non_verified_role = discord.utils.get(member.guild.roles, name="Non-Verified")
        if not non_verified_role:
            non_verified_role = await member.guild.create_role(
                name="Non-Verified",
                color=discord.Color.red(),
                reason="Role for unverified members"
            )
        
        # Create verified role if it doesn't exist
        verified_role = discord.utils.get(member.guild.roles, name="Verified")
        if not verified_role:
            verified_role = await member.guild.create_role(
                name="Verified",
                color=discord.Color.green(),
                reason="Role for verified members"
            )
        
        await member.add_roles(non_verified_role)
        
        # Update channel permissions for the new member
        await flipper_channel.set_permissions(member, read_messages=True, send_messages=False)
        
        # Create welcome message with buttons
        embed = discord.Embed(
            title="🎮 Welcome to FlipperBot!",
            description=(
                "Welcome to our community! To get started:\n\n"
                "1️⃣ Click the **Verify** button to authenticate your account\n"
                "2️⃣ Check the **Q&A** section for helpful information\n"
                "3️⃣ Once verified, you'll get access to all features!"
            ),
            color=discord.Color.blue()
        )
        
        view = discord.ui.View(timeout=None)
        
        # Verify button
        verify_button = discord.ui.Button(
            style=getattr(discord.ButtonStyle, config.get('buttons.verify_style', 'green').lower()),
            label=config.get('buttons.verify_label', 'Verify'),
            custom_id='verify_button',
            emoji=config.get('buttons.verify_emoji', '✅')
        )
        
        # Q&A button
        qa_button = discord.ui.Button(
            style=getattr(discord.ButtonStyle, config.get('buttons.qa_style', 'blurple').lower()),
            label=config.get('buttons.qa_label', 'Q&A'),
            custom_id='qa_button',
            emoji=config.get('buttons.qa_emoji', '❓')
        )
        
        view.add_item(verify_button)
        view.add_item(qa_button)
        
        await flipper_channel.send(embed=embed, view=view)
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.type == discord.InteractionType.component:
            return
            
        if interaction.custom_id == 'verify_button':
            await self.handle_verify(interaction)
        elif interaction.custom_id == 'qa_button':
            await self.handle_qa(interaction)
    
    async def handle_verify(self, interaction: discord.Interaction):
        try:
            # Generate OAuth URL
            auth_url = self.auth_manager.generate_oauth_url()
            
            embed = discord.Embed(
                title="✅ Account Verification",
                description=(
                    "Please follow these steps to verify your account:\n\n"
                    "1️⃣ **Microsoft Account Login**\n"
                    f"• [Click here to login with Microsoft]({auth_url})\n\n"
                    "2️⃣ **Two-Factor Authentication**\n"
                    "• After Microsoft login, you'll set up 2FA\n"
                    "• Use any authenticator app (Google, Microsoft, etc.)\n\n"
                    "3️⃣ **Completion**\n"
                    "• Once verified, you'll get the Verified role\n"
                    "• Access to all bot features will be unlocked\n\n"
                    "ℹ️ Need help? Click the Q&A button!"
                ),
                color=discord.Color.green()
            )
            embed.set_footer(text="This verification link will expire in 10 minutes")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Log verification attempt
            logger.info(f"User {interaction.user.id} started verification process")
            
        except Exception as e:
            logger.error(f"Error in verification process: {e}")
            error_embed = discord.Embed(
                title="❌ Verification Error",
                description="An error occurred during verification. Please try again later or contact support.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    async def handle_qa(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="❓ Frequently Asked Questions",
            description="Here are some common questions and answers about FlipperBot:",
            color=discord.Color.blue()
        )
        
        # Add FAQ items
        embed.add_field(
            name="What is FlipperBot?",
            value="FlipperBot is a Discord bot that helps you find profitable flipping opportunities in Hypixel Skyblock. It monitors the auction house and alerts you to potential profits.",
            inline=False
        )
        
        embed.add_field(
            name="How do I get verified?",
            value=(
                "1. Click the Verify button\n"
                "2. Login with your Microsoft account\n"
                "3. Set up 2FA using any authenticator app\n"
                "4. Wait for verification to complete"
            ),
            inline=False
        )
        
        embed.add_field(
            name="What features are available?",
            value=(
                "• Real-time flip notifications\n"
                "• Profit calculations\n"
                "• Custom flip filters\n"
                "• Market analysis\n"
                "• And much more!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Need more help?",
            value="If you need additional assistance, please contact our support team or check the documentation.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ButtonInteractions(bot)) 