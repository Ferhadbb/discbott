import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import psutil
import logging
import aiohttp
import asyncio
from typing import Dict, Optional
from config_manager import ConfigManager

logger = logging.getLogger('monitoring')
config = ConfigManager()

class Monitoring(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()
        self.last_error = None
        self.error_count = 0
        self.api_status: Dict[str, bool] = {}
        self.status_message: Optional[discord.Message] = None
        
        # Start background tasks
        self.health_check.start()
        self.update_status.start()
        self.cleanup_old_status.start()

    def cog_unload(self):
        self.health_check.cancel()
        self.update_status.cancel()
        self.cleanup_old_status.cancel()

    async def get_status_channel(self) -> Optional[discord.TextChannel]:
        """Get the status channel from config"""
        channel_id = config.get('channels.notifications.status')
        if channel_id:
            return self.bot.get_channel(int(channel_id))
        return None

    @tasks.loop(minutes=5)
    async def health_check(self):
        """Perform regular health checks"""
        try:
            # Check bot connection
            if not self.bot.is_ready():
                logger.error("Bot not ready, attempting reconnect...")
                await self.attempt_reconnect()
                return

            # Check API connections
            apis_to_check = {
                'Hypixel': 'https://api.hypixel.net',
                'Discord': 'https://discord.com/api/v10'
            }

            async with aiohttp.ClientSession() as session:
                for api_name, url in apis_to_check.items():
                    try:
                        async with session.get(url) as response:
                            self.api_status[api_name] = response.status == 200
                    except Exception as e:
                        logger.error(f"Error checking {api_name} API: {e}")
                        self.api_status[api_name] = False

            # Check system resources
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            if cpu_percent > 90 or memory.percent > 90 or disk.percent > 90:
                await self.alert_high_resource_usage(cpu_percent, memory.percent, disk.percent)

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.last_error = str(e)
            self.error_count += 1
            await self.alert_error("Health Check Failed", str(e))

    async def attempt_reconnect(self):
        """Attempt to reconnect the bot"""
        retries = 5
        while retries > 0:
            try:
                await self.bot.close()
                await self.bot.start(config.get('bot.token'))
                logger.info("Successfully reconnected!")
                break
            except Exception as e:
                logger.error(f"Reconnect attempt failed: {e}")
                retries -= 1
                await asyncio.sleep(60)

    @tasks.loop(minutes=1)
    async def update_status(self):
        """Update status message with current bot statistics"""
        try:
            channel = await self.get_status_channel()
            if not channel:
                return

            embed = await self.create_status_embed()
            
            if self.status_message:
                try:
                    await self.status_message.edit(embed=embed)
                except discord.NotFound:
                    self.status_message = await channel.send(embed=embed)
            else:
                self.status_message = await channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error updating status: {e}")

    async def create_status_embed(self) -> discord.Embed:
        """Create status embed with current statistics"""
        uptime = datetime.utcnow() - self.start_time
        
        embed = discord.Embed(
            title="🤖 Bot Status Dashboard",
            description="[View Uptime Dashboard](https://stats.uptimerobot.com/your-dashboard)",  # Add your UptimeRobot public dashboard URL
            color=discord.Color.green() if not self.last_error else discord.Color.red(),
            timestamp=datetime.utcnow()
        )

        # Basic Stats
        embed.add_field(
            name="⏱️ Uptime",
            value=str(uptime).split('.')[0],
            inline=True
        )
        embed.add_field(
            name="📊 Latency",
            value=f"{round(self.bot.latency * 1000)}ms",
            inline=True
        )
        embed.add_field(
            name="❌ Errors (24h)",
            value=str(self.error_count),
            inline=True
        )

        # System Resources
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        embed.add_field(
            name="💻 System Resources",
            value=f"CPU: {cpu_percent}%\nRAM: {memory.percent}%\nDisk: {disk.percent}%",
            inline=False
        )

        # API Status
        api_status_text = "\n".join(
            f"{name}: {'🟢' if status else '🔴'}"
            for name, status in self.api_status.items()
        )
        embed.add_field(
            name="🌐 API Status",
            value=api_status_text or "No API checks yet",
            inline=False
        )

        # Last Error
        if self.last_error:
            embed.add_field(
                name="⚠️ Last Error",
                value=f"```{self.last_error}```",
                inline=False
            )

        return embed

    @tasks.loop(hours=24)
    async def cleanup_old_status(self):
        """Clean up old status messages"""
        try:
            channel = await self.get_status_channel()
            if not channel:
                return

            async for message in channel.history(limit=100):
                if message != self.status_message and message.author == self.bot.user:
                    await message.delete()
                    await asyncio.sleep(1)  # Avoid rate limits

        except Exception as e:
            logger.error(f"Error cleaning up status messages: {e}")

    async def alert_error(self, title: str, error: str):
        """Send error alert to admin channel"""
        try:
            admin_channel_id = config.get('channels.admin.logs')
            if admin_channel_id:
                channel = self.bot.get_channel(int(admin_channel_id))
                if channel:
                    embed = discord.Embed(
                        title=f"⚠️ {title}",
                        description=f"```{error}```",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error sending alert: {e}")

    async def alert_high_resource_usage(self, cpu: float, memory: float, disk: float):
        """Alert admins about high resource usage"""
        embed = discord.Embed(
            title="⚠️ High Resource Usage Alert",
            description="System resources are running high!",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="CPU Usage", value=f"{cpu}%", inline=True)
        embed.add_field(name="Memory Usage", value=f"{memory}%", inline=True)
        embed.add_field(name="Disk Usage", value=f"{disk}%", inline=True)
        
        await self.alert_error("High Resource Usage", 
                             f"CPU: {cpu}%\nMemory: {memory}%\nDisk: {disk}%")

    @health_check.before_loop
    @update_status.before_loop
    @cleanup_old_status.before_loop
    async def before_task(self):
        """Wait for bot to be ready before starting tasks"""
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Monitoring(bot)) 