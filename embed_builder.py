import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict
from datetime import datetime
import json
from config_manager import ConfigManager
import logging

logger = logging.getLogger('embed_builder')
config = ConfigManager()

class EmbedBuilderModal(discord.ui.Modal, title="Create Custom Embed"):
    title = discord.ui.TextInput(
        label="Embed Title",
        placeholder="Enter the title for your embed...",
        required=True,
        max_length=256
    )
    
    description = discord.ui.TextInput(
        label="Embed Description",
        placeholder="Enter the main text of your embed...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=4000
    )
    
    image_url = discord.ui.TextInput(
        label="Image URL (optional)",
        placeholder="Enter a URL for the main image...",
        required=False,
        max_length=1000
    )
    
    thumbnail_url = discord.ui.TextInput(
        label="Thumbnail URL (optional)",
        placeholder="Enter a URL for the thumbnail...",
        required=False,
        max_length=1000
    )
    
    color = discord.ui.TextInput(
        label="Color (hex code)",
        placeholder="#ff0000",
        default="#5865F2",
        required=True,
        max_length=7
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Convert hex color to int
            color_hex = self.color.value.strip('#')
            color_int = int(color_hex, 16)
            
            # Create embed
            embed = discord.Embed(
                title=self.title.value,
                description=self.description.value,
                color=color_int,
                timestamp=datetime.utcnow()
            )
            
            # Add image if provided
            if self.image_url.value:
                embed.set_image(url=self.image_url.value)
            
            # Add thumbnail if provided
            if self.thumbnail_url.value:
                embed.set_thumbnail(url=self.thumbnail_url.value)
            
            # Store the embed for later use
            builder_cog = interaction.client.get_cog('EmbedBuilder')
            if builder_cog:
                await builder_cog.save_embed(
                    interaction.user.id,
                    self.title.value,
                    {
                        'title': self.title.value,
                        'description': self.description.value,
                        'color': self.color.value,
                        'image_url': self.image_url.value,
                        'thumbnail_url': self.thumbnail_url.value
                    }
                )
            
            # Show preview
            preview_view = EmbedPreviewView()
            await interaction.response.send_message(
                "Here's how your embed looks:",
                embed=embed,
                view=preview_view,
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                "Invalid color hex code! Please use format #RRGGBB",
                ephemeral=True
            )

class EmbedFieldModal(discord.ui.Modal, title="Add Embed Field"):
    name = discord.ui.TextInput(
        label="Field Name",
        placeholder="Enter the field name...",
        required=True,
        max_length=256
    )
    
    value = discord.ui.TextInput(
        label="Field Value",
        placeholder="Enter the field content...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1024
    )
    
    inline = discord.ui.TextInput(
        label="Inline (true/false)",
        placeholder="true",
        default="true",
        required=True,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            inline = self.inline.value.lower() == 'true'
            
            # Get the original embed
            original_message = interaction.message
            original_embed = original_message.embeds[0]
            
            # Add the new field
            original_embed.add_field(
                name=self.name.value,
                value=self.value.value,
                inline=inline
            )
            
            # Update the message
            preview_view = EmbedPreviewView()
            await interaction.message.edit(embed=original_embed, view=preview_view)
            await interaction.response.send_message("Field added!", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"Error adding field: {str(e)}",
                ephemeral=True
            )

class EmbedPreviewView(discord.ui.View):
    def __init__(self):
        super().__init__()
    
    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.primary)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EmbedFieldModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Send", style=discord.ButtonStyle.success)
    async def send_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Where would you like to send this embed? Use `/send_embed` in the desired channel.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Save Template", style=discord.ButtonStyle.secondary)
    async def save_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        builder_cog = interaction.client.get_cog('EmbedBuilder')
        if builder_cog:
            embed = interaction.message.embeds[0]
            template_name = f"template_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            await builder_cog.save_embed(interaction.user.id, template_name, embed.to_dict())
            await interaction.response.send_message(
                f"Template saved as `{template_name}`!",
                ephemeral=True
            )

class EmbedBuilder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stored_embeds: Dict[int, Dict[str, dict]] = {}  # user_id -> {name: embed_data}
    
    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to use embed builder"""
        return (
            str(interaction.user.id) == config.get('access.owner_id') or
            config.is_admin(str(interaction.user.id))
        )
    
    async def save_embed(self, user_id: int, name: str, embed_data: dict):
        """Save embed data for a user"""
        if user_id not in self.stored_embeds:
            self.stored_embeds[user_id] = {}
        self.stored_embeds[user_id][name] = embed_data
    
    @app_commands.command(name="create_embed", description="Create a custom embed")
    async def create_embed(self, interaction: discord.Interaction):
        if not await self._check_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command!",
                ephemeral=True
            )
            return
        
        modal = EmbedBuilderModal()
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="send_embed", description="Send a saved embed to the current channel")
    @app_commands.describe(template_name="Name of the saved embed template")
    async def send_embed(
        self,
        interaction: discord.Interaction,
        template_name: str
    ):
        if not await self._check_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command!",
                ephemeral=True
            )
            return
        
        try:
            user_embeds = self.stored_embeds.get(interaction.user.id, {})
            embed_data = user_embeds.get(template_name)
            
            if not embed_data:
                await interaction.response.send_message(
                    f"No template found with name: {template_name}",
                    ephemeral=True
                )
                return
            
            # Convert hex color to int if needed
            if isinstance(embed_data.get('color'), str):
                color_hex = embed_data['color'].strip('#')
                embed_data['color'] = int(color_hex, 16)
            
            # Create and send embed
            embed = discord.Embed.from_dict(embed_data)
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message(
                "Embed sent!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error sending embed: {e}")
            await interaction.response.send_message(
                "Error sending embed. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="list_embeds", description="List your saved embed templates")
    async def list_embeds(self, interaction: discord.Interaction):
        if not await self._check_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command!",
                ephemeral=True
            )
            return
        
        user_embeds = self.stored_embeds.get(interaction.user.id, {})
        if not user_embeds:
            await interaction.response.send_message(
                "You don't have any saved embed templates!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="Your Saved Embed Templates",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        for name in user_embeds.keys():
            embed.add_field(name=name, value="Use `/send_embed template_name:`" + name, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="delete_embed", description="Delete a saved embed template")
    @app_commands.describe(template_name="Name of the template to delete")
    async def delete_embed(
        self,
        interaction: discord.Interaction,
        template_name: str
    ):
        if not await self._check_permission(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command!",
                ephemeral=True
            )
            return
        
        user_embeds = self.stored_embeds.get(interaction.user.id, {})
        if template_name in user_embeds:
            del user_embeds[template_name]
            await interaction.response.send_message(
                f"Template `{template_name}` deleted!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"No template found with name: {template_name}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(EmbedBuilder(bot)) 