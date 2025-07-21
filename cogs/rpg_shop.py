
import discord
from discord.ext import commands
import math
from utils.helpers import create_embed, format_number
from config import COLORS, is_module_enabled
from rpg_data.game_data import ITEMS, RARITY_COLORS
import logging

logger = logging.getLogger(__name__)

class ShopMainView(discord.ui.View):
    """Main shop interface with category buttons."""

    def __init__(self, user_id: str, rpg_core):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.rpg_core = rpg_core

    @discord.ui.button(label="⚔️ Weapons", style=discord.ButtonStyle.primary, emoji="⚔️", row=0)
    async def weapons_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        view = ShopCategoryView(self.user_id, "weapon", self.rpg_core)
        embed = view.create_category_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🛡️ Armor", style=discord.ButtonStyle.primary, emoji="🛡️", row=0)
    async def armor_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        view = ShopCategoryView(self.user_id, "armor", self.rpg_core)
        embed = view.create_category_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🧪 Consumables", style=discord.ButtonStyle.primary, emoji="🧪", row=0)
    async def consumables_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        view = ShopCategoryView(self.user_id, "consumable", self.rpg_core)
        embed = view.create_category_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="💎 Accessories", style=discord.ButtonStyle.primary, emoji="💎", row=0)
    async def accessories_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        view = ShopCategoryView(self.user_id, "accessory", self.rpg_core)
        embed = view.create_category_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="✨ Artifacts", style=discord.ButtonStyle.primary, emoji="✨", row=1)
    async def artifacts_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        view = ShopCategoryView(self.user_id, "artifact", self.rpg_core)
        embed = view.create_category_embed()
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="💰 My Gold", style=discord.ButtonStyle.secondary, emoji="💰", row=1)
    async def check_gold(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        player_data = self.rpg_core.get_player_data(self.user_id)
        if not player_data:
            await interaction.response.send_message("❌ Character not found!", ephemeral=True)
            return

        embed = discord.Embed(
            title="💰 Your Wealth",
            description=f"**Current Gold:** `{format_number(player_data['gold'])}` 💰\n\n"
                       f"📊 **Inventory Stats:**\n"
                       f"• Total Items: `{sum(player_data.get('inventory', {}).values())}`\n"
                       f"• Unique Items: `{len(player_data.get('inventory', {}))}`\n"
                       f"• Estimated Worth: `{format_number(int(player_data['gold'] * 1.3))}` 💰",
            color=COLORS['gold']
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ShopCategoryView(discord.ui.View):
    """Category view with item browsing and navigation."""

    def __init__(self, user_id: str, category: str, rpg_core):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.category = category
        self.rpg_core = rpg_core
        self.current_page = 0
        self.items_per_page = 8
        
        # Filter items by category
        self.category_items = []
        for item_key, item_data in ITEMS.items():
            if item_data.get('type') == category:
                self.category_items.append((item_key, item_data))
        
        # Sort by price and rarity
        rarity_order = {'common': 1, 'uncommon': 2, 'rare': 3, 'epic': 4, 'legendary': 5, 'mythical': 6, 'divine': 7, 'cosmic': 8}
        self.category_items.sort(key=lambda x: (x[1].get('price', 0), rarity_order.get(x[1].get('rarity', 'common'), 1)))

    def create_category_embed(self):
        """Create the category listing embed."""
        max_pages = math.ceil(len(self.category_items) / self.items_per_page)
        
        embed = discord.Embed(
            title=f"🛒 {self.category.title()} Shop",
            description=f"Browse and purchase {self.category}s for your adventure!",
            color=COLORS['primary']
        )

        if not self.category_items:
            embed.add_field(
                name="😔 No Items Available",
                value="This category is currently empty. Check back later!",
                inline=False
            )
            return embed

        # Calculate page items
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.category_items))
        page_items = self.category_items[start_idx:end_idx]

        # Create item list
        items_text = ""
        for i, (item_key, item_data) in enumerate(page_items, start=1):
            rarity = item_data.get('rarity', 'common')
            rarity_emoji = {'common': '⚪', 'uncommon': '🟢', 'rare': '🔵', 'epic': '🟣', 'legendary': '🟠', 'mythical': '🔴', 'divine': '⭐', 'cosmic': '🌟'}.get(rarity, '⚪')
            
            # Format item stats
            stats = []
            if item_data.get('attack'):
                stats.append(f"⚔️{item_data['attack']}")
            if item_data.get('defense'):
                stats.append(f"🛡️{item_data['defense']}")
            if item_data.get('heal_amount'):
                stats.append(f"❤️{item_data['heal_amount']}")
            
            stats_str = f" `({'/'.join(stats)})`" if stats else ""
            
            items_text += f"`{start_idx + i}.` {rarity_emoji} **{item_data['name']}**{stats_str}\n"
            items_text += f"     💰 `{format_number(item_data.get('price', 0))}` gold\n"
            items_text += f"     📝 {item_data.get('description', 'No description')[:50]}{'...' if len(item_data.get('description', '')) > 50 else ''}\n\n"

        embed.add_field(
            name=f"📦 Available {self.category.title()}s",
            value=items_text or "No items to display.",
            inline=False
        )

        embed.set_footer(text=f"Page {self.current_page + 1} of {max_pages} | Use dropdown to select items")

        return embed

    @discord.ui.select(placeholder="🛍️ Select an item to view details...", min_values=1, max_values=1)
    async def item_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        # Populate select with current page items
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.category_items))
        page_items = self.category_items[start_idx:end_idx]

        select.options = []
        for i, (item_key, item_data) in enumerate(page_items):
            rarity_emoji = {'common': '⚪', 'uncommon': '🟢', 'rare': '🔵', 'epic': '🟣', 'legendary': '🟠', 'mythical': '🔴'}.get(item_data.get('rarity', 'common'), '⚪')
            select.options.append(
                discord.SelectOption(
                    label=item_data['name'][:25],
                    value=item_key,
                    description=f"{format_number(item_data.get('price', 0))} gold",
                    emoji=rarity_emoji
                )
            )

        if select.values:
            item_key = select.values[0]
            view = ItemDetailsView(self.user_id, item_key, self.rpg_core, self.category)
            embed = view.create_item_embed()
            await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary, row=2)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        if self.current_page > 0:
            self.current_page -= 1
            embed = self.create_category_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary, row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        max_pages = math.ceil(len(self.category_items) / self.items_per_page)
        if self.current_page < max_pages - 1:
            self.current_page += 1
            embed = self.create_category_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏠 Main Shop", style=discord.ButtonStyle.success, row=2)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        player_data = self.rpg_core.get_player_data(self.user_id)
        view = ShopMainView(self.user_id, self.rpg_core)
        embed = self.create_main_shop_embed(player_data)
        await interaction.response.edit_message(embed=embed, view=view)

    def create_main_shop_embed(self, player_data):
        """Create main shop embed."""
        embed = discord.Embed(
            title="🛒 Plagg's Cheese & Combat Shop",
            description="**Welcome to the finest shop in all dimensions!**\n\n"
                       "Here you can find everything from powerful weapons to magical cheese wheels.\n"
                       "Choose a category below to browse available items.\n\n"
                       "💰 **Shop Features:**\n"
                       "• Quality guaranteed by Plagg himself\n"
                       "• Instant delivery to your inventory\n"
                       "• Cheese-powered discounts available\n"
                       "• No returns (destroyed items stay destroyed)",
            color=COLORS['primary']
        )
        
        embed.add_field(
            name="🏪 Categories",
            value="⚔️ **Weapons** - Swords, bows, staves\n"
                  "🛡️ **Armor** - Protection and shields\n"
                  "🧪 **Consumables** - Potions and elixirs\n"
                  "💎 **Accessories** - Rings and amulets\n"
                  "✨ **Artifacts** - Legendary items",
            inline=True
        )
        
        if player_data:
            embed.add_field(
                name="💰 Your Funds",
                value=f"**Gold:** `{format_number(player_data['gold'])}`\n"
                      f"**Items:** `{sum(player_data.get('inventory', {}).values())}`",
                inline=True
            )
        
        embed.set_footer(text="Click a category button to start shopping!")
        return embed

class ItemDetailsView(discord.ui.View):
    """Detailed item view with purchase options."""

    def __init__(self, user_id: str, item_key: str, rpg_core, category: str):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.item_key = item_key
        self.rpg_core = rpg_core
        self.category = category
        self.quantity = 1

    def create_item_embed(self):
        """Create detailed item embed."""
        item_data = ITEMS.get(self.item_key, {})
        player_data = self.rpg_core.get_player_data(self.user_id)
        
        if not item_data:
            return create_embed("Error", "Item not found!", COLORS['error'])

        rarity = item_data.get('rarity', 'common')
        rarity_color = RARITY_COLORS.get(rarity, COLORS['primary'])
        rarity_emoji = {'common': '⚪', 'uncommon': '🟢', 'rare': '🔵', 'epic': '🟣', 'legendary': '🟠', 'mythical': '🔴', 'divine': '⭐', 'cosmic': '🌟'}.get(rarity, '⚪')

        embed = discord.Embed(
            title=f"{rarity_emoji} {item_data['name']}",
            description=f"**{item_data.get('description', 'A mysterious item with unknown properties.')}**",
            color=rarity_color
        )

        # Item stats
        stats_text = ""
        if item_data.get('attack'):
            stats_text += f"⚔️ **Attack:** `{item_data['attack']}`\n"
        if item_data.get('defense'):
            stats_text += f"🛡️ **Defense:** `{item_data['defense']}`\n"
        if item_data.get('heal_amount'):
            stats_text += f"❤️ **Healing:** `{item_data['heal_amount']} HP`\n"
        if item_data.get('mana_amount'):
            stats_text += f"💙 **Mana:** `{item_data['mana_amount']} MP`\n"

        if stats_text:
            embed.add_field(name="📊 Stats", value=stats_text, inline=True)

        # Item info
        info_text = f"**Type:** `{item_data['type'].title()}`\n"
        info_text += f"**Rarity:** `{rarity.title()}`\n"
        info_text += f"**Price:** `{format_number(item_data.get('price', 0))}` 💰"
        
        embed.add_field(name="ℹ️ Details", value=info_text, inline=True)

        # Purchase info
        total_cost = item_data.get('price', 0) * self.quantity
        can_afford = player_data['gold'] >= total_cost if player_data else False
        
        purchase_text = f"**Quantity:** `{self.quantity}`\n"
        purchase_text += f"**Total Cost:** `{format_number(total_cost)}` 💰\n"
        if player_data:
            purchase_text += f"**Your Gold:** `{format_number(player_data['gold'])}` 💰\n"
            if can_afford:
                purchase_text += f"**After Purchase:** `{format_number(player_data['gold'] - total_cost)}` 💰"
            else:
                needed = total_cost - player_data['gold']
                purchase_text += f"❌ **Need:** `{format_number(needed)}` more gold"

        embed.add_field(name="🛒 Purchase", value=purchase_text, inline=False)

        # Special effects
        if item_data.get('effects'):
            effects_text = ""
            for effect in item_data['effects']:
                effects_text += f"• {effect}\n"
            embed.add_field(name="✨ Special Effects", value=effects_text, inline=False)

        return embed

    @discord.ui.select(
        placeholder="📦 Select quantity...",
        options=[
            discord.SelectOption(label="1x", value="1", emoji="1️⃣"),
            discord.SelectOption(label="5x", value="5", emoji="5️⃣"),
            discord.SelectOption(label="10x", value="10", emoji="🔟"),
            discord.SelectOption(label="25x", value="25", emoji="📦"),
            discord.SelectOption(label="50x", value="50", emoji="📦"),
        ]
    )
    async def quantity_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your purchase!", ephemeral=True)
            return

        self.quantity = int(select.values[0])
        embed = self.create_item_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✅ Purchase", style=discord.ButtonStyle.success, emoji="💰", row=2)
    async def confirm_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your purchase!", ephemeral=True)
            return

        await interaction.response.defer()

        player_data = self.rpg_core.get_player_data(self.user_id)
        if not player_data:
            embed = create_embed("Error", "Character not found!", COLORS['error'])
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=None)
            return

        item_data = ITEMS.get(self.item_key, {})
        total_cost = item_data.get('price', 0) * self.quantity

        if player_data['gold'] < total_cost:
            needed = total_cost - player_data['gold']
            embed = create_embed(
                "Insufficient Funds",
                f"You need `{format_number(needed)}` more gold to purchase `{self.quantity}x {item_data.get('name', 'Unknown Item')}`!",
                COLORS['error']
            )
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=None)
            return

        # Process purchase
        player_data['gold'] -= total_cost
        if 'inventory' not in player_data:
            player_data['inventory'] = {}
        
        if self.item_key in player_data['inventory']:
            player_data['inventory'][self.item_key] += self.quantity
        else:
            player_data['inventory'][self.item_key] = self.quantity

        self.rpg_core.save_player_data(self.user_id, player_data)

        embed = discord.Embed(
            title="✅ Purchase Successful!",
            description=f"**Congratulations on your purchase!**",
            color=COLORS['success']
        )
        
        embed.add_field(
            name="🛍️ Items Purchased",
            value=f"`{self.quantity}x` **{item_data.get('name', 'Unknown')}**",
            inline=True
        )
        
        embed.add_field(
            name="💰 Transaction",
            value=f"**Paid:** `{format_number(total_cost)}` gold\n"
                  f"**Remaining:** `{format_number(player_data['gold'])}` gold",
            inline=True
        )
        
        embed.add_field(
            name="📦 Inventory",
            value=f"You now have `{player_data['inventory'][self.item_key]}x` {item_data.get('name', 'Unknown')}",
            inline=False
        )

        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=None)

    @discord.ui.button(label="🔙 Back", style=discord.ButtonStyle.secondary, emoji="⬅️", row=2)
    async def back_to_category(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This isn't your shop!", ephemeral=True)
            return

        view = ShopCategoryView(self.user_id, self.category, self.rpg_core)
        embed = view.create_category_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class RPGShop(commands.Cog):
    """Interactive RPG shop system with comprehensive navigation."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="shop", aliases=["store", "buy"])
    async def shop(self, ctx):
        """Open the interactive shop interface with improved navigation."""
        if not is_module_enabled("rpg", ctx.guild.id):
            return

        rpg_core = self.bot.get_cog('RPGCore')
        if not rpg_core:
            await ctx.send("❌ RPG system not loaded.")
            return

        player_data = rpg_core.get_player_data(str(ctx.author.id))
        if not player_data:
            embed = create_embed("No Character", "Use `$startrpg` to begin your adventure!", COLORS['error'])
            await ctx.send(embed=embed)
            return

        view = ShopMainView(str(ctx.author.id), rpg_core)
        
        embed = discord.Embed(
            title="🛒 Plagg's Cheese & Combat Shop",
            description="**Welcome to the finest shop in all dimensions!**\n\n"
                       "Here you can find everything from powerful weapons to magical cheese wheels.\n"
                       "Choose a category below to browse available items.\n\n"
                       "💰 **Shop Features:**\n"
                       "• Quality guaranteed by Plagg himself\n"
                       "• Instant delivery to your inventory\n"
                       "• Cheese-powered discounts available\n"
                       "• No returns (destroyed items stay destroyed)",
            color=COLORS['primary']
        )
        
        embed.add_field(
            name="🏪 Categories",
            value="⚔️ **Weapons** - Swords, bows, staves\n"
                  "🛡️ **Armor** - Protection and shields\n"
                  "🧪 **Consumables** - Potions and elixirs\n"
                  "💎 **Accessories** - Rings and amulets\n"
                  "✨ **Artifacts** - Legendary items",
            inline=True
        )
        
        embed.add_field(
            name="💰 Your Funds",
            value=f"**Gold:** `{format_number(player_data['gold'])}`\n"
                  f"**Items:** `{sum(player_data.get('inventory', {}).values())}`",
            inline=True
        )
        
        embed.set_footer(text="Click a category button to start shopping!")

        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(RPGShop(bot))
