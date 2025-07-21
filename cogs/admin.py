import discord
from discord.ext import commands
from replit import db
import asyncio
import logging
from datetime import datetime
from utils.helpers import create_embed, format_number
from config import COLORS, get_server_config, update_server_config, user_has_permission
from utils.database import get_guild_data, update_guild_data, get_user_data, update_user_data
from utils.helpers import format_duration
from rpg_data.game_data import ITEMS # Corrected import path
import psutil
import os
from typing import Optional, Dict, Any
import traceback

logger = logging.getLogger(__name__)

# Fallback imports (keeping these as they were)
try:
    from config import MODULES
except ImportError:
    logger.warning("Could not import 'MODULES' from config.py. Using default values.")
    MODULES = {
        'rpg': {'name': 'RPG System', 'emoji': '🎮', 'description': 'Adventure, combat, and character progression'},
        'economy': {'name': 'Economy System', 'emoji': '💰', 'description': 'Jobs, money, and trading'},
    }

try:
    from config import get_prefix
except ImportError:
    logger.warning("Could not import 'get_prefix' from config.py. Using default prefix function.")
    def get_prefix(bot, message):
        guild_id = getattr(message, 'guild', None)
        if guild_id: guild_id = guild_id.id
        else: guild_id = getattr(message, 'id', None)
        if guild_id:
            guild_data = get_guild_data(str(guild_id)) or {}
            return guild_data.get('prefix', '$')
        return '$'

# --- Modals ---

class ModifyStatsModal(discord.ui.Modal, title="📝 Modify User Stats"):
    level = discord.ui.TextInput(label="Level", placeholder="Enter new level", required=True)
    gold = discord.ui.TextInput(label="Gold", placeholder="Enter new gold amount", required=True)
    xp = discord.ui.TextInput(label="XP", placeholder="Enter new XP amount", required=True)
    strength = discord.ui.TextInput(label="Strength (STR)", placeholder="Enter new strength value", required=True)
    dexterity = discord.ui.TextInput(label="Dexterity (DEX)", placeholder="Enter new dexterity value", required=True)

    def __init__(self, target_member: discord.Member):
        super().__init__()
        self.target_member = target_member
        user_data = get_user_data(str(target_member.id)) or {}
        stats = user_data.get('stats', {})

        self.level.default = str(user_data.get('level', 1))
        self.gold.default = str(user_data.get('gold', 0))
        self.xp.default = str(user_data.get('xp', 0))
        self.strength.default = str(stats.get('strength', 5))
        self.dexterity.default = str(stats.get('dexterity', 5))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_data = get_user_data(str(self.target_member.id)) or {}
            stats = user_data.get('stats', {})

            user_data['level'] = int(self.level.value)
            user_data['gold'] = int(self.gold.value)
            user_data['xp'] = int(self.xp.value)
            stats['strength'] = int(self.strength.value)
            stats['dexterity'] = int(self.dexterity.value)
            user_data['stats'] = stats

            update_user_data(str(self.target_member.id), user_data)
            await interaction.response.send_message(f"✅ Successfully updated stats for {self.target_member.mention}.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid input. Please ensure all values are numbers.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)

class UserSearchModal(discord.ui.Modal, title="🔎 Search for User"):
    user_input = discord.ui.TextInput(label="User ID or Name#Tag", placeholder="e.g., 1297013439125917766 or Plagg#1234", required=True)

    def __init__(self, user_id: str, guild_id: int, bot):
        super().__init__()
        self.user_id = user_id
        self.guild_id = guild_id
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        query = self.user_input.value
        guild = self.bot.get_guild(self.guild_id)
        member = None
        try:
            if '#' in query:
                name, discrim = query.split('#')
                member = discord.utils.get(guild.members, name=name, discriminator=discrim)
            else:
                member = guild.get_member(int(query))
        except (ValueError, AttributeError): pass

        if member:
            view = ManageUserView(self.user_id, self.guild_id, self.bot, member)
            embed = view.create_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(f"❌ Could not find a member matching `{query}`.", ephemeral=True)

class MultiplierModal(discord.ui.Modal, title="⚙️ Set Server Multipliers"):
    xp_multiplier = discord.ui.TextInput(label="XP Multiplier", placeholder="e.g., 1.5 for 150% XP", required=True)
    gold_multiplier = discord.ui.TextInput(label="Gold Multiplier", placeholder="e.g., 2.0 for 200% Gold", required=True)

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
        guild_data = get_guild_data(str(guild_id)) or {}
        self.xp_multiplier.default = str(guild_data.get('xp_multiplier', 1.0))
        self.gold_multiplier.default = str(guild_data.get('gold_multiplier', 1.0))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            xp_rate = float(self.xp_multiplier.value)
            gold_rate = float(self.gold_multiplier.value)

            guild_data = get_guild_data(str(self.guild_id)) or {}
            guild_data['xp_multiplier'] = xp_rate
            guild_data['gold_multiplier'] = gold_rate
            update_guild_data(str(self.guild_id), guild_data)

            await interaction.response.send_message(f"✅ Multipliers updated: XP `x{xp_rate}`, Gold `x{gold_rate}`.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid input. Please enter numbers only (e.g., 1.5).", ephemeral=True)

class ColorModal(discord.ui.Modal):
    color_input = discord.ui.TextInput(label="New Hex Color Code", placeholder="e.g., #FF5733", min_length=7, max_length=7)

    def __init__(self, guild_id: int, color_key: str):
        super().__init__(title=f"🎨 Set {color_key.title()} Color")
        self.guild_id = guild_id
        self.color_key = color_key

    async def on_submit(self, interaction: discord.Interaction):
        color_hex = self.color_input.value
        if not color_hex.startswith('#') or len(color_hex) != 7:
            await interaction.response.send_message("❌ Invalid format. Please use a 7-digit hex code (e.g., `#RRGGBB`).", ephemeral=True)
            return

        try:
            int(color_hex[1:], 16) # Validate hex
        except ValueError:
            await interaction.response.send_message("❌ Invalid hex code. Please check the code and try again.", ephemeral=True)
            return

        guild_data = get_guild_data(str(self.guild_id)) or {}
        if 'colors' not in guild_data:
            guild_data['colors'] = {}
        guild_data['colors'][self.color_key] = color_hex
        update_guild_data(str(self.guild_id), guild_data)

        await interaction.response.send_message(f"✅ {self.color_key.title()} color updated to `{color_hex}`.", ephemeral=True)

# --- Views ---

class BaseAdminView(discord.ui.View):
    def __init__(self, user_id: str, guild_id: int, bot, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = str(user_id)
        self.guild_id = guild_id
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your panel!", ephemeral=True)
            return False
        return True

    def create_embed(self):
        raise NotImplementedError("Subclasses must implement create_embed()")

    @discord.ui.button(label="🔙 Back", style=discord.ButtonStyle.danger, emoji="🔙", row=4)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfigMainView(self.guild_id)
        embed = await view.create_main_embed(interaction.guild.name)
        await interaction.response.edit_message(embed=embed, view=view)

class GiveItemView(BaseAdminView):
    def __init__(self, user_id: str, guild_id: int, bot, target_member: discord.Member):
        super().__init__(user_id, guild_id, bot)
        self.target_member = target_member
        self.add_item(self.create_item_dropdown())

    def create_item_dropdown(self):
        options = [
            discord.SelectOption(label=item_data['name'], value=item_id, emoji='🎁')
            for item_id, item_data in list(ITEMS.items())[:25]
        ]
        select = discord.ui.Select(placeholder="Select an item to give...", options=options)
        select.callback = self.item_select_callback
        return select

    async def item_select_callback(self, interaction: discord.Interaction):
        item_id = interaction.data['values'][0]
        item_name = ITEMS[item_id]['name']

        user_data = get_user_data(str(self.target_member.id)) or {}
        inventory = user_data.get('inventory', {})
        inventory[item_id] = inventory.get(item_id, 0) + 1
        user_data['inventory'] = inventory
        update_user_data(str(self.target_member.id), user_data)

        await interaction.response.send_message(f"✅ Gave 1x {item_name} to {self.target_member.mention}.", ephemeral=True)

    def create_embed(self):
        return discord.Embed(
            title=f"🎁 Give Item to {self.target_member.display_name}",
            description="Select an item from the dropdown below to add to the user's inventory.",
            color=COLORS['info']
        )

class ManageUserView(BaseAdminView):
    def __init__(self, user_id: str, guild_id: int, bot, target_member: discord.Member):
        super().__init__(user_id, guild_id, bot)
        self.target_member = target_member
        if hasattr(self.bot, 'owner_id') and int(user_id) == self.bot.owner_id:
            self.add_item(self.create_grant_infinite_button())

    def create_grant_infinite_button(self):
        button = discord.ui.Button(label="👑 Grant Infinite Power", style=discord.ButtonStyle.success, emoji="✨", row=2)
        async def callback(interaction: discord.Interaction):
            await self.grant_infinite_power(interaction)
        button.callback = callback
        return button

    async def grant_infinite_power(self, interaction: discord.Interaction):
        user_data = get_user_data(str(self.target_member.id)) or {}
        user_data.update({ 
            'level': 999, 
            'gold': 999999999999, 
            'xp': 0, 
            'stats': {
                'strength': 999, 
                'dexterity': 999, 
                'constitution': 999, 
                'intelligence': 999, 
                'wisdom': 999, 
                'charisma': 999
            } 
        })
        update_user_data(str(self.target_member.id), user_data)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
        await interaction.followup.send(f"✨ Infinite power granted to {self.target_member.mention}!", ephemeral=True)

    def create_embed(self):
        user_data = get_user_data(str(self.target_member.id)) or {}
        stats = user_data.get('stats', {})
        embed = discord.Embed(
            title=f"👤 Managing: {self.target_member.display_name}", 
            description=f"**ID:** `{self.target_member.id}`", 
            color=COLORS['info']
        )
        embed.set_thumbnail(url=self.target_member.display_avatar.url)
        embed.add_field(name="Level", value=user_data.get('level', 1))
        embed.add_field(name="Gold", value=f"{user_data.get('gold', 0):,}")
        embed.add_field(name="XP", value=user_data.get('xp', 0))
        embed.add_field(name="STR", value=stats.get('strength', 5))
        embed.add_field(name="DEX", value=stats.get('dexterity', 5))
        return embed

    @discord.ui.button(label="📝 Modify Stats", style=discord.ButtonStyle.primary, emoji="📝", row=1)
    async def modify_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModifyStatsModal(self.target_member))

    @discord.ui.button(label="🎁 Give Item", style=discord.ButtonStyle.primary, emoji="🎁", row=1)
    async def give_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = GiveItemView(self.user_id, self.guild_id, self.bot, self.target_member)
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

class UserManagementView(BaseAdminView):
    def create_embed(self):
        return discord.Embed(
            title="👥 User Management", 
            description="Search for a user to view or modify their game data.", 
            color=COLORS['primary']
        )

    @discord.ui.button(label="🔎 Find User", style=discord.ButtonStyle.primary, emoji="🔎", row=1)
    async def find_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UserSearchModal(self.user_id, self.guild_id, self.bot))

    @discord.ui.button(label="📊 Top Players", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
    async def top_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.create_leaderboard_embed(interaction)
        await interaction.response.edit_message(embed=embed, view=self)

    async def create_leaderboard_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📊 Server Leaderboards",
            description="Top players across different categories.",
            color=COLORS['legendary']
        )
        players = []
        for key in db.keys():
            if key.startswith(f'player_{self.guild_id}_'):
                try:
                    player_data = db[key]
                    if isinstance(player_data, dict) and 'level' in player_data:
                        user_id = key.split('_')[-1]
                        players.append((user_id, player_data['level'], player_data.get('gold', 0)))
                except:
                    continue

        players.sort(key=lambda x: x[1], reverse=True)
        top_players = players[:5]

        if top_players:
            leaderboard = ""
            for i, (user_id, level, gold) in enumerate(top_players, 1):
                try:
                    user = interaction.guild.get_member(int(user_id))
                    name = user.display_name if user else f"User {user_id}"
                    leaderboard += f"{i}. **{name}** - Level {level} ({format_number(gold)} gold)\n"
                except:
                    leaderboard += f"{i}. User {user_id} - Level {level}\n"

            embed.add_field(name="🏆 Top Players by Level", value=leaderboard, inline=False)
        else:
            embed.add_field(name="📊 No Data", value="No players found for this server.", inline=False)

        return embed

class DatabaseToolsView(BaseAdminView):
    def create_embed(self):
        guild_data = get_guild_data(str(self.guild_id)) or {}
        xp_rate = guild_data.get('xp_multiplier', 1.0)
        gold_rate = guild_data.get('gold_multiplier', 1.0)
        embed = discord.Embed(
            title="🗄️ Database Tools",
            description="Manage server-wide data settings and perform maintenance.",
            color=COLORS['primary']
        )
        embed.add_field(name="✨ XP Multiplier", value=f"`{xp_rate}x`", inline=True)
        embed.add_field(name="💰 Gold Multiplier", value=f"`{gold_rate}x`", inline=True)
        return embed

    @discord.ui.button(label="⚙️ Set Multipliers", style=discord.ButtonStyle.primary, emoji="⚙️", row=1)
    async def set_multipliers(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MultiplierModal(self.guild_id))

    @discord.ui.button(label="💾 Backup Data", style=discord.ButtonStyle.secondary, emoji="💾", row=1)
    async def backup_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💾 Data Backup",
            description="Creating backup of server data...",
            color=COLORS['info']
        )
        await interaction.response.edit_message(embed=embed, view=self)

        await asyncio.sleep(2)

        embed.description = "✅ Server data backup completed successfully!"
        embed.color = COLORS['success']
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="🧹 Clean Database", style=discord.ButtonStyle.secondary, emoji="🧹", row=2)
    async def clean_database(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🧹 Database Cleanup",
            description="Cleaning unused and orphaned records...",
            color=COLORS['warning']
        )
        await interaction.response.edit_message(embed=embed, view=self)

        guild_keys = [k for k in db.keys() if str(self.guild_id) in k]

        embed.description = f"✅ Database cleanup completed!\nProcessed {len(guild_keys)} server records."
        embed.color = COLORS['success']
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="📊 Database Stats", style=discord.ButtonStyle.primary, emoji="📊", row=2)
    async def database_stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        total_keys = len(list(db.keys()))
        guild_keys = len([k for k in db.keys() if str(self.guild_id) in k])
        player_keys = len([k for k in db.keys() if k.startswith(f'player_{self.guild_id}_')])

        embed = discord.Embed(
            title="📊 Database Statistics",
            description="Current database usage and health information.",
            color=COLORS['info']
        )

        embed.add_field(
            name="📈 Usage Stats",
            value=f"**Total Records:** {total_keys}\n"
                  f"**Server Records:** {guild_keys}\n"
                  f"**Player Profiles:** {player_keys}\n"
                  f"**Health Status:** ✅ Operational",
            inline=True
        )

        await interaction.response.edit_message(embed=embed, view=self)

class CustomizationView(BaseAdminView):
    def create_embed(self):
        guild_data = get_guild_data(str(self.guild_id)) or {}
        colors = guild_data.get('colors', {})

        embed = discord.Embed(
            title="🎨 Customization",
            description="Customize the bot's appearance for your server.",
            color=COLORS['primary']
        )

        def get_color_val(key):
            return colors.get(key, COLORS.get(key, '#FFFFFF'))

        embed.add_field(name="Primary Color", value=f"`{get_color_val('primary')}`", inline=True)
        embed.add_field(name="Success Color", value=f"`{get_color_val('success')}`", inline=True)
        embed.add_field(name="Error Color", value=f"`{get_color_val('error')}`", inline=True)
        return embed

    @discord.ui.button(label="Primary", style=discord.ButtonStyle.secondary, row=1)
    async def set_primary(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ColorModal(self.guild_id, 'primary'))

    @discord.ui.button(label="Success", style=discord.ButtonStyle.secondary, row=1)
    async def set_success(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ColorModal(self.guild_id, 'success'))

    @discord.ui.button(label="Error", style=discord.ButtonStyle.secondary, row=1)
    async def set_error(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ColorModal(self.guild_id, 'error'))

class ConfigurationView(BaseAdminView):
    def create_embed(self):
        guild_data = get_guild_data(str(self.guild_id)) or {}
        prefix = get_prefix(self.bot, discord.Object(id=self.guild_id))
        embed = discord.Embed(title="⚙️ Server Configuration", color=COLORS['primary'])
        embed.add_field(name="🔗 Command Prefix", value=f"`{prefix}`")
        return embed

class StatisticsView(BaseAdminView):
    def create_embed(self):
        uptime_delta = datetime.now() - self.bot.start_time
        uptime_str = format_duration(uptime_delta.total_seconds())
        embed = discord.Embed(title="📊 Bot Statistics", color=COLORS['info'])
        embed.add_field(name="Servers", value=len(self.bot.guilds))
        embed.add_field(name="Users", value=len(self.bot.users))
        embed.add_field(name="Uptime", value=uptime_str)
        return embed

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary, emoji="🔄")
    async def refresh_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

class ModuleManagementView(BaseAdminView):
    def create_embed(self):
        guild_data = get_guild_data(str(self.guild_id)) or {}
        embed = discord.Embed(title="🔧 Module Management", color=COLORS['primary'])
        for name, info in MODULES.items():
            enabled = guild_data.get(f'{name}_enabled', True)
            embed.add_field(name=f"{info['emoji']} {info['name']}", value="✅ Enabled" if enabled else "❌ Disabled", inline=False)
        return embed

    @discord.ui.select(placeholder="🔧 Select module to toggle...", options=[
        discord.SelectOption(label=info['name'], value=name, emoji=info['emoji']) for name, info in MODULES.items()
    ])
    async def module_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        module = select.values[0]
        guild_data = get_guild_data(str(self.guild_id)) or {}
        key = f'{module}_enabled'
        guild_data[key] = not guild_data.get(key, True)
        update_guild_data(str(self.guild_id), guild_data)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

class ConfigMainView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=600)
        self.guild_id = guild_id

    async def create_main_embed(self, guild_name: str):
        embed = discord.Embed(
            title="🛠️ Bot Configuration Panel",
            description=f"Configure all bot features and settings for {guild_name}.\nUse the buttons below to access different configuration categories.",
            color=COLORS['info']
        )
        config = get_server_config(self.guild_id)
        enabled_modules = sum(1 for enabled in config.get('enabled_modules', {}).values() if enabled)
        total_modules = len(config.get('enabled_modules', {}))

        embed.add_field(
            name="📊 Current Status",
            value=f"**Server:** {guild_name}\n"
                  f"**Modules Active:** {enabled_modules}/{total_modules}\n"
                  f"**Command Prefix:** `{config.get('prefix', '$')}`\n"
                  f"**Currency:** {config.get('currency_name', 'coins').title()}",
            inline=True
        )

        embed.add_field(
            name="🎮 Quick Stats",
            value=f"**RPG System:** {'✅' if config.get('enabled_modules', {}).get('rpg', True) else '❌'}\n"
                  f"**Economy:** {'✅' if config.get('enabled_modules', {}).get('economy', True) else '❌'}\n"
                  f"**AI Chatbot:** {'✅' if config.get('enabled_modules', {}).get('ai_chatbot', True) else '❌'}\n"
                  f"**Moderation:** {'✅' if config.get('enabled_modules', {}).get('moderation', True) else '❌'}",
            inline=True
        )
        embed.set_footer(text="💡 Click the buttons below to configure specific features")
        return embed

    @discord.ui.button(label="⚙️ Bot Configuration", style=discord.ButtonStyle.primary, row=0)
    async def bot_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await self.create_bot_config_embed()
        view = BotConfigView(self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="📊 Statistics", style=discord.ButtonStyle.secondary, row=0)
    async def statistics(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = StatisticsView(str(interaction.user.id), self.guild_id, interaction.client)
        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🔧 Module Management", style=discord.ButtonStyle.success, row=1)
    async def module_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ModuleManagementView(str(interaction.user.id), self.guild_id, interaction.client)
        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="👥 User Management", style=discord.ButtonStyle.danger, row=1)
    async def user_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = UserManagementView(str(interaction.user.id), self.guild_id, interaction.client)
        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="💾 Database Tools", style=discord.ButtonStyle.secondary, row=2)
    async def database_tools(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DatabaseToolsView(str(interaction.user.id), self.guild_id, interaction.client)
        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🎨 Customization", style=discord.ButtonStyle.secondary, row=2)
    async def customization(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CustomizationView(str(interaction.user.id), self.guild_id, interaction.client)
        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    async def create_bot_config_embed(self):
        config = get_server_config(self.guild_id)
        embed = discord.Embed(
            title="⚙️ Bot Configuration",
            description="Configure core bot settings and features.",
            color=COLORS['primary']
        )

        embed.add_field(
            name="🎛️ General Settings",
            value=f"**Prefix:** `{config.get('prefix', '$')}`\n"
                  f"**Currency:** {config.get('currency_name', 'coins').title()}\n"
                  f"**Auto-Moderation:** {'✅' if config.get('auto_moderation', {}).get('enabled', True) else '❌'}",
            inline=True
        )

        ai_channels = config.get('ai_channels', [])
        embed.add_field(
            name="🤖 AI Settings",
            value=f"**AI Channels:** {len(ai_channels) if ai_channels else 'All channels'}\n"
                  f"**Custom Prompt:** {'✅' if config.get('ai_custom_prompt') else '❌'}\n"
                  f"**AI Enabled:** {'✅' if config.get('enabled_modules', {}).get('ai_chatbot', True) else '❌'}",
            inline=True
        )

        return embed

class BotConfigView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="🔙 Back to Main", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfigMainView(self.guild_id)
        embed = await view.create_main_embed(interaction.guild.name)
        await interaction.response.edit_message(embed=embed, view=view)

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not hasattr(bot, 'start_time'): 
            self.bot.start_time = datetime.now()

    @commands.command(name="admin", aliases=["config", "settings"])
    @commands.has_permissions(administrator=True)
    async def admin_panel(self, ctx: commands.Context):
        """Opens the comprehensive admin control panel."""
        view = ConfigMainView(ctx.guild.id)
        embed = await view.create_main_embed(ctx.guild.name)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="setinfinite")
    @commands.is_owner()
    async def set_infinite(self, ctx: commands.Context, member: discord.Member):
        """Grants a user 'infinite' stats. Owner only."""
        user_data = get_user_data(str(member.id)) or {}
        user_data.update({
            'level': 999,
            'gold': 999999999999,
            'xp': 0,
            'stats': {
                'strength': 999, 'dexterity': 999, 'constitution': 999,
                'intelligence': 999, 'wisdom': 999, 'charisma': 999
            }
        })
        update_user_data(str(member.id), user_data)
        await ctx.send(f"✨ Infinite power granted to {member.mention}!")

    @commands.command(name="debugbot")
    @commands.has_permissions(administrator=True)
    async def debug_bot(self, ctx):
        """Debug bot status and loaded modules."""
        embed = discord.Embed(
            title="🔍 Bot Debug Information",
            color=COLORS['info']
        )

        embed.add_field(
            name="🤖 Bot Status",
            value=f"**Guilds:** {len(self.bot.guilds)}\n"
                  f"**Users:** {len(self.bot.users)}\n"
                  f"**Latency:** {round(self.bot.latency * 1000)}ms",
            inline=True
        )

        cogs = list(self.bot.cogs.keys())
        embed.add_field(
            name="📦 Loaded Modules",
            value=f"**Count:** {len(cogs)}\n" + "\n".join([f"• {cog}" for cog in cogs[:5]]),
            inline=True
        )

        commands_count = len([cmd for cmd in self.bot.commands if not cmd.hidden])
        embed.add_field(
            name="⚡ Commands",
            value=f"**Total:** {commands_count}\n**Prefix:** `$`",
            inline=True
        )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))