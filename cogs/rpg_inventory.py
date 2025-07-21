
import discord
from discord.ext import commands
from replit import db
import math
from typing import Dict, Any, List, Optional
from datetime import datetime

from config import COLORS, is_module_enabled
from utils.helpers import create_embed, format_number
from rpg_data.game_data import ITEMS, RARITY_COLORS
import logging

logger = logging.getLogger(__name__)

# Plagg's inventory categories with his signature complaints
INVENTORY_CATEGORIES = {
    'all': {
        'name': '📦 All Items',
        'emoji': '📦',
        'description': "Everything you've hoarded. It's heavier than it looks."
    },
    'weapons': {
        'name': '⚔️ Weapons', 
        'emoji': '⚔️',
        'description': "Pointy things that aren't cheese knives. Disappointing."
    },
    'armor': {
        'name': '🛡️ Armor',
        'emoji': '🛡️', 
        'description': "Heavy metal that won't protect you from cheese withdrawal."
    },
    'accessories': {
        'name': '💍 Accessories',
        'emoji': '💍',
        'description': "Shiny baubles. None of them smell like Camembert."
    },
    'kwami_artifacts': {
        'name': '✨ Kwami Artifacts',
        'emoji': '✨',
        'description': "Mystical items with actual power. Still not cheese though."
    },
    'consumables': {
        'name': '🧪 Consumables',
        'emoji': '🧪',
        'description': "Things you can actually eat. Finally, some potential!"
    },
    'materials': {
        'name': '🧱 Materials',
        'emoji': '🧱',
        'description': "Crafting junk. Can you craft cheese with these? Probably not."
    }
}

class InventoryView(discord.ui.View):
    """Plagg's reluctant inventory management system."""
    
    def __init__(self, user_id, rpg_core):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.rpg_core = rpg_core
        self.current_category = 'all'
        self.current_page = 0
        self.items_per_page = 8
        self.selected_item = None
        self.in_inspection_mode = False
        
        # Load player data
        self.player_data = rpg_core.get_player_data(user_id)
        if not self.player_data:
            return
            
        # Initialize view
        self.update_components()
    
    def get_player_inventory(self):
        """Get the player's inventory with proper formatting."""
        return self.player_data.get('inventory', {})
    
    def get_equipped_items(self):
        """Get currently equipped items."""
        return self.player_data.get('equipment', {})
    
    def filter_items_by_category(self, category):
        """Filter inventory items by category."""
        inventory = self.get_player_inventory()
        if category == 'all':
            return inventory
        
        # Filter by item type (this would need to be expanded based on your item data structure)
        filtered = {}
        for item_key, quantity in inventory.items():
            item_data = ITEMS.get(item_key, {})
            item_type = item_data.get('type', 'materials').lower()
            
            # Map item types to categories
            if category == 'weapons' and item_type in ['weapon', 'sword', 'bow', 'staff']:
                filtered[item_key] = quantity
            elif category == 'armor' and item_type in ['armor', 'helmet', 'chestplate', 'boots']:
                filtered[item_key] = quantity
            elif category == 'accessories' and item_type in ['accessory', 'ring', 'necklace', 'charm']:
                filtered[item_key] = quantity
            elif category == 'kwami_artifacts' and item_type in ['kwami_artifact', 'miraculous']:
                filtered[item_key] = quantity
            elif category == 'consumables' and item_type in ['consumable', 'potion', 'food', 'cheese']:
                filtered[item_key] = quantity
            elif category == 'materials' and item_type in ['material', 'resource', 'component']:
                filtered[item_key] = quantity
                
        return filtered
    
    def get_paginated_items(self):
        """Get items for the current page."""
        filtered_items = self.filter_items_by_category(self.current_category)
        items_list = list(filtered_items.items())
        
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        
        return items_list[start_idx:end_idx], len(items_list)
    
    def create_main_inventory_embed(self):
        """Create the main inventory display embed."""
        category_info = INVENTORY_CATEGORIES[self.current_category]
        
        embed = discord.Embed(
            title="🎒 Your Bag of Mostly Useless Junk",
            description=f"*\"Alright, I lugged this thing all the way here. Don't take too long, this is cutting into my nap time. "
                       f"Pick a category, I guess.\"*\n\n**Current Category:** {category_info['name']}\n"
                       f"*{category_info['description']}*",
            color=COLORS['warning']
        )
        
        # Get paginated items
        page_items, total_items = self.get_paginated_items()
        
        if not page_items:
            embed.add_field(
                name="📭 Empty Category",
                value="*\"Well, would you look at that. Nothing here. Maybe try hoarding more stuff?\"*",
                inline=False
            )
        else:
            # Calculate pagination info
            total_pages = math.ceil(total_items / self.items_per_page)
            current_page_display = self.current_page + 1
            
            # Build item list
            item_list = ""
            for i, (item_key, quantity) in enumerate(page_items, 1):
                item_data = ITEMS.get(item_key, {'name': item_key.replace('_', ' ').title(), 'rarity': 'common'})
                rarity = item_data.get('rarity', 'common')
                rarity_emoji = self.get_rarity_emoji(rarity)
                item_name = item_data.get('name', item_key.replace('_', ' ').title())
                
                quantity_text = f" (x{quantity})" if quantity > 1 else ""
                item_list += f"{i}. {rarity_emoji} **{item_name}**{quantity_text}\n"
            
            embed.add_field(
                name=f"📋 Items ({current_page_display}/{total_pages})",
                value=item_list or "*Empty*",
                inline=False
            )
            
            # Add player stats summary
            equipped = self.get_equipped_items()
            equipped_count = len([item for item in equipped.values() if item])
            
            embed.add_field(
                name="⚡ Quick Stats",
                value=f"**Total Items:** {sum(self.get_player_inventory().values())}\n"
                      f"**Equipped Items:** {equipped_count}\n"
                      f"**Gold:** {format_number(self.player_data.get('gold', 0))}",
                inline=True
            )
        
        embed.set_footer(text="💡 Use the dropdowns to select categories and items | 🧀 Still no cheese in sight...")
        return embed
    
    def create_item_inspection_embed(self, item_key):
        """Create the detailed item inspection view."""
        item_data = ITEMS.get(item_key, {})
        inventory = self.get_player_inventory()
        quantity = inventory.get(item_key, 0)
        
        # Get item info
        item_name = item_data.get('name', item_key.replace('_', ' ').title())
        rarity = item_data.get('rarity', 'common')
        rarity_emoji = self.get_rarity_emoji(rarity)
        rarity_color = RARITY_COLORS.get(rarity, COLORS['secondary'])
        
        embed = discord.Embed(
            title=f"{rarity_emoji} {item_name}",
            color=rarity_color
        )
        
        # Item type and basic info
        item_type = item_data.get('type', 'Unknown').title()
        subtype = item_data.get('subtype', '')
        if subtype:
            type_text = f"{item_type} - {subtype.title()}"
        else:
            type_text = item_type
            
        embed.add_field(
            name="📋 Item Info",
            value=f"**Type:** {type_text}\n**Rarity:** {rarity.title()}\n**Quantity:** {quantity}",
            inline=True
        )
        
        # Stats (if any)
        stats = item_data.get('stats', {})
        if stats:
            stat_list = []
            for stat, value in stats.items():
                if value > 0:
                    stat_list.append(f"+{value} {stat.replace('_', ' ').title()}")
                elif value < 0:
                    stat_list.append(f"{value} {stat.replace('_', ' ').title()}")
            
            if stat_list:
                embed.add_field(
                    name="📊 Stats",
                    value="\n".join(stat_list),
                    inline=True
                )
        
        # Special effects
        special_effect = item_data.get('special_effect')
        if special_effect:
            embed.add_field(
                name="✨ Special Effect",
                value=special_effect,
                inline=False
            )
        
        # Set bonus (for artifacts)
        set_bonus = item_data.get('set_bonus')
        if set_bonus:
            embed.add_field(
                name="🔮 Set Bonus",
                value=set_bonus,
                inline=False
            )
        
        # Plagg's commentary
        plagg_comments = self.get_plagg_commentary(item_key, item_data)
        embed.add_field(
            name="🧀 Plagg's Commentary",
            value=f"*\"{plagg_comments}\"*",
            inline=False
        )
        
        # Value info
        sell_price = item_data.get('sell_price', 0)
        if sell_price > 0:
            embed.add_field(
                name="💰 Value",
                value=f"Sell Price: {format_number(sell_price)} Gold",
                inline=True
            )
        
        embed.set_footer(text="💡 Use the buttons below to interact with this item")
        return embed
    
    def get_rarity_emoji(self, rarity):
        """Get emoji for item rarity."""
        rarity_emojis = {
            'common': '⚪',
            'uncommon': '🟢', 
            'rare': '🔵',
            'epic': '🟣',
            'legendary': '🟠',
            'mythical': '🔴',
            'divine': '✨',
            'plagg_cheese': '🧀'
        }
        return rarity_emojis.get(rarity.lower(), '⚪')
    
    def get_plagg_commentary(self, item_key, item_data):
        """Generate Plagg's sarcastic commentary for items."""
        item_type = item_data.get('type', '').lower()
        rarity = item_data.get('rarity', '').lower()
        
        # Cheese items get special treatment
        if 'cheese' in item_key.lower() or item_type == 'cheese':
            return "NOW WE'RE TALKING! Finally, something worthwhile in this mess! This is the only item that matters!"
        
        # Type-specific comments
        if item_type in ['weapon', 'sword', 'bow']:
            comments = [
                "It's pointy. Great. Can you use it to slice cheese? That's the only stat I care about.",
                "Another weapon. Because clearly, what this world needs is more ways to fight and less cheese.",
                "Sharp and dangerous. Unlike cheese, which is soft and wonderful.",
                "I suppose it's decent for poking things. But can it poke holes in cheese for better aging?"
            ]
        elif item_type in ['armor', 'helmet', 'chestplate']:
            comments = [
                "This hunk of metal is supposed to protect you. A wheel of Camembert is bigger, tastier, and probably more protective.",
                "Heavy, uncomfortable, and definitely not cheese-scented. What's the point?",
                "Great, more armor. Because the real threat isn't cheese deprivation, apparently.",
                "It might stop a sword, but it won't stop my complaints about the lack of cheese here."
            ]
        elif item_type in ['potion', 'consumable']:
            if 'health' in item_key.lower():
                comments = [
                    "Smells awful. If you're that hurt, maybe you should try fighting less and napping more.",
                    "Red liquid that supposedly heals you. I prefer red wax on cheese wheels, personally.",
                    "Medicinal and boring. Where's the cheese-flavored healing potion?"
                ]
            else:
                comments = [
                    "At least this one you can actually consume. Still not cheese though.",
                    "Consumable items are the only category with potential. Shame this isn't cheese.",
                    "You can eat this, which puts it above 90% of your other junk."
                ]
        elif rarity in ['legendary', 'mythical', 'divine']:
            comments = [
                "Ooh, fancy rarity. I bet it still doesn't taste as good as aged Camembert.",
                "Legendary, huh? The only true legend is the perfect cheese wheel.",
                "Very impressive. Would be more impressive if it were cheese-related.",
                "Mythical power, mundane flavor. That's my guess anyway."
            ]
        else:
            comments = [
                "More junk for your collection. When do we get to the cheese section?",
                "I'm sure this seemed important when you picked it up. It's not.",
                "Another item that's definitely not cheese. Color me surprised.",
                "This is taking up space that could be used for cheese storage.",
                "Mildly interesting. Emphasis on 'mildly'."
            ]
        
        import random
        return random.choice(comments)
    
    def update_components(self):
        """Update the view components based on current mode."""
        self.clear_items()
        
        if not self.in_inspection_mode:
            # Main inventory mode
            self.add_item(CategorySelect(self))
            
            # Only add item select if there are items
            page_items, total_items = self.get_paginated_items()
            if page_items:
                self.add_item(ItemSelect(self, page_items))
            
            # Pagination buttons
            if total_items > self.items_per_page:
                self.add_item(PreviousPageButton(self))
                self.add_item(NextPageButton(self))
            
            self.add_item(CloseInventoryButton(self))
        else:
            # Item inspection mode
            item_data = ITEMS.get(self.selected_item, {})
            item_type = item_data.get('type', '').lower()
            
            # Equipment button for equippable items
            if item_type in ['weapon', 'armor', 'accessory', 'kwami_artifact']:
                self.add_item(EquipItemButton(self))
                self.add_item(CompareItemButton(self))
            
            # Use button for consumables
            if item_type in ['consumable', 'potion', 'food', 'cheese']:
                self.add_item(UseItemButton(self))
            
            # Sell button (always available)
            self.add_item(SellItemButton(self))
            
            # Back to inventory button
            self.add_item(BackToInventoryButton(self))

class CategorySelect(discord.ui.Select):
    """Dropdown for selecting inventory categories."""
    
    def __init__(self, inventory_view):
        self.inventory_view = inventory_view
        
        options = []
        for cat_key, cat_data in INVENTORY_CATEGORIES.items():
            options.append(discord.SelectOption(
                label=cat_data['name'],
                value=cat_key,
                emoji=cat_data['emoji'],
                description=cat_data['description'][:100],
                default=(cat_key == inventory_view.current_category)
            ))
        
        super().__init__(
            placeholder="🧀 Select a category... *sigh*",
            options=options,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        self.inventory_view.current_category = self.values[0]
        self.inventory_view.current_page = 0  # Reset to first page
        self.inventory_view.update_components()
        
        embed = self.inventory_view.create_main_inventory_embed()
        await interaction.response.edit_message(embed=embed, view=self.inventory_view)

class ItemSelect(discord.ui.Select):
    """Dropdown for selecting specific items."""
    
    def __init__(self, inventory_view, page_items):
        self.inventory_view = inventory_view
        
        options = []
        for i, (item_key, quantity) in enumerate(page_items):
            if len(options) >= 25:  # Discord limit
                break
                
            item_data = ITEMS.get(item_key, {'name': item_key.replace('_', ' ').title(), 'rarity': 'common'})
            item_name = item_data.get('name', item_key.replace('_', ' ').title())
            rarity = item_data.get('rarity', 'common')
            rarity_emoji = inventory_view.get_rarity_emoji(rarity)
            
            # Truncate name if too long
            display_name = item_name[:45] + "..." if len(item_name) > 45 else item_name
            quantity_text = f" (x{quantity})" if quantity > 1 else ""
            
            options.append(discord.SelectOption(
                label=f"{display_name}{quantity_text}",
                value=item_key,
                emoji=rarity_emoji,
                description=f"{rarity.title()} {item_data.get('type', 'Item').title()}"
            ))
        
        super().__init__(
            placeholder="🔍 Select an item to inspect...",
            options=options if options else [discord.SelectOption(label="No items", value="none")],
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        if self.values[0] == "none":
            await interaction.response.defer()
            return
        
        self.inventory_view.selected_item = self.values[0]
        self.inventory_view.in_inspection_mode = True
        self.inventory_view.update_components()
        
        embed = self.inventory_view.create_item_inspection_embed(self.values[0])
        await interaction.response.edit_message(embed=embed, view=self.inventory_view)

class PreviousPageButton(discord.ui.Button):
    """Navigate to previous page."""
    
    def __init__(self, inventory_view):
        self.inventory_view = inventory_view
        super().__init__(
            label="Previous",
            emoji="⬅️",
            style=discord.ButtonStyle.secondary,
            disabled=(inventory_view.current_page <= 0),
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        self.inventory_view.current_page = max(0, self.inventory_view.current_page - 1)
        self.inventory_view.update_components()
        
        embed = self.inventory_view.create_main_inventory_embed()
        await interaction.response.edit_message(embed=embed, view=self.inventory_view)

class NextPageButton(discord.ui.Button):
    """Navigate to next page."""
    
    def __init__(self, inventory_view):
        self.inventory_view = inventory_view
        page_items, total_items = inventory_view.get_paginated_items()
        max_pages = math.ceil(total_items / inventory_view.items_per_page) if total_items > 0 else 1
        
        super().__init__(
            label="Next",
            emoji="➡️", 
            style=discord.ButtonStyle.secondary,
            disabled=(inventory_view.current_page >= max_pages - 1),
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        page_items, total_items = self.inventory_view.get_paginated_items()
        max_pages = math.ceil(total_items / self.inventory_view.items_per_page) if total_items > 0 else 1
        
        self.inventory_view.current_page = min(max_pages - 1, self.inventory_view.current_page + 1)
        self.inventory_view.update_components()
        
        embed = self.inventory_view.create_main_inventory_embed()
        await interaction.response.edit_message(embed=embed, view=self.inventory_view)

class CloseInventoryButton(discord.ui.Button):
    """Close the inventory."""
    
    def __init__(self, inventory_view):
        super().__init__(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎒 Inventory Closed",
            description="*\"Finally! Now I can get back to important things. Like napping. And thinking about cheese.\"*",
            color=COLORS['success']
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

class EquipItemButton(discord.ui.Button):
    """Equip the selected item."""
    
    def __init__(self, inventory_view):
        super().__init__(
            label="Equip",
            emoji="✅",
            style=discord.ButtonStyle.success,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        item_key = self.inventory_view.selected_item
        item_data = ITEMS.get(item_key, {})
        item_name = item_data.get('name', item_key.replace('_', ' ').title())
        
        # Get equipment slot
        item_type = item_data.get('type', '').lower()
        equipment_slots = {
            'weapon': 'weapon',
            'sword': 'weapon', 
            'bow': 'weapon',
            'staff': 'weapon',
            'helmet': 'helmet',
            'chestplate': 'chestplate',
            'armor': 'chestplate',
            'boots': 'boots',
            'accessory': 'accessory',
            'ring': 'ring',
            'necklace': 'necklace',
            'kwami_artifact': 'kwami_artifact'
        }
        
        slot = equipment_slots.get(item_type)
        if not slot:
            await interaction.response.send_message("This item cannot be equipped!", ephemeral=True)
            return
        
        # Handle equipment swap
        player_data = self.inventory_view.player_data
        equipment = player_data.get('equipment', {})
        inventory = player_data.get('inventory', {})
        
        # Remove from inventory
        if inventory.get(item_key, 0) > 1:
            inventory[item_key] -= 1
        else:
            inventory.pop(item_key, None)
        
        # Unequip current item if any
        old_item = equipment.get(slot)
        if old_item:
            inventory[old_item] = inventory.get(old_item, 0) + 1
        
        # Equip new item
        equipment[slot] = item_key
        
        # Save changes
        player_data['equipment'] = equipment
        player_data['inventory'] = inventory
        self.inventory_view.rpg_core.save_player_data(self.inventory_view.user_id, player_data)
        
        # Plagg's response
        plagg_responses = [
            f"Fine, I swapped it. You look slightly more ridiculous now, if that was even possible.",
            f"There, it's equipped. Happy? Can we please find some cheese now?",
            f"Congratulations, you're now wearing slightly different junk.",
            f"Equipped. Now you're 0.1% more likely to survive. Don't get cocky.",
        ]
        
        import random
        response = random.choice(plagg_responses)
        
        embed = discord.Embed(
            title="✅ Item Equipped!",
            description=f"*\"{response}\"*\n\n**{item_name}** has been equipped!",
            color=COLORS['success']
        )
        
        if old_item:
            old_item_data = ITEMS.get(old_item, {})
            old_name = old_item_data.get('name', old_item.replace('_', ' ').title())
            embed.add_field(
                name="🔄 Previous Item",
                value=f"**{old_name}** was returned to your inventory.",
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed, view=None)

class UseItemButton(discord.ui.Button):
    """Use/consume the selected item."""
    
    def __init__(self, inventory_view):
        super().__init__(
            label="Use",
            emoji="🧪",
            style=discord.ButtonStyle.primary,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        item_key = self.inventory_view.selected_item
        item_data = ITEMS.get(item_key, {})
        item_name = item_data.get('name', item_key.replace('_', ' ').title())
        
        # Check if item exists in inventory
        player_data = self.inventory_view.player_data
        inventory = player_data.get('inventory', {})
        
        if inventory.get(item_key, 0) <= 0:
            await interaction.response.send_message("You don't have this item!", ephemeral=True)
            return
        
        # Process item effects
        effect_result = self.process_item_effect(item_key, item_data, player_data)
        
        # Remove item from inventory
        if inventory[item_key] > 1:
            inventory[item_key] -= 1
        else:
            inventory.pop(item_key, None)
        
        # Save changes
        self.inventory_view.rpg_core.save_player_data(self.inventory_view.user_id, player_data)
        
        embed = discord.Embed(
            title="🧪 Item Used!",
            description=f"**{item_name}** has been consumed!\n\n{effect_result}",
            color=COLORS['success']
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    def process_item_effect(self, item_key, item_data, player_data):
        """Process the effects of using an item."""
        effect_type = item_data.get('effect_type')
        resources = player_data.get('resources', {})
        
        if 'cheese' in item_key.lower():
            # Special cheese handling
            hp_heal = item_data.get('heal_amount', 50)
            resources['hp'] = min(resources.get('max_hp', 100), resources.get('hp', 100) + hp_heal)
            return f"*\"NOW WE'RE TALKING! That cheese was absolutely divine! +{hp_heal} HP restored!\"*"
        
        elif effect_type == 'heal':
            heal_amount = item_data.get('heal_amount', 25)
            resources['hp'] = min(resources.get('max_hp', 100), resources.get('hp', 100) + heal_amount)
            return f"*\"Tastes awful, but I guess it worked. +{heal_amount} HP restored.\"*"
        
        elif effect_type == 'mana':
            mana_amount = item_data.get('mana_amount', 20)
            resources['mana'] = min(resources.get('max_mana', 50), resources.get('mana', 50) + mana_amount)
            return f"*\"Magical and boring. +{mana_amount} Mana restored.\"*"
        
        elif effect_type == 'buff':
            # Handle temporary buffs (would need a buff system)
            return f"*\"I suppose you feel slightly more capable now. For a few minutes.\"*"
        
        else:
            return f"*\"You consumed it. Something probably happened. I wasn't paying attention.\"*"

class CompareItemButton(discord.ui.Button):
    """Compare item with currently equipped."""
    
    def __init__(self, inventory_view):
        super().__init__(
            label="Compare",
            emoji="⚖️",
            style=discord.ButtonStyle.secondary,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        item_key = self.inventory_view.selected_item
        item_data = ITEMS.get(item_key, {})
        item_name = item_data.get('name', item_key.replace('_', ' ').title())
        
        # Get equipment slot
        item_type = item_data.get('type', '').lower()
        equipment_slots = {
            'weapon': 'weapon',
            'sword': 'weapon',
            'armor': 'chestplate',
            'helmet': 'helmet',
            'boots': 'boots'
        }
        
        slot = equipment_slots.get(item_type)
        if not slot:
            await interaction.response.send_message("Cannot compare this item type!", ephemeral=True)
            return
        
        # Get currently equipped item
        equipment = self.inventory_view.player_data.get('equipment', {})
        equipped_key = equipment.get(slot)
        
        if not equipped_key:
            embed = discord.Embed(
                title="⚖️ Item Comparison",
                description=f"*\"There's nothing equipped in that slot to compare with. This {item_name} would be an upgrade by default.\"*",
                color=COLORS['info']
            )
            await interaction.response.edit_message(embed=embed, view=self.inventory_view)
            return
        
        # Create comparison embed
        equipped_data = ITEMS.get(equipped_key, {})
        equipped_name = equipped_data.get('name', equipped_key.replace('_', ' ').title())
        
        embed = discord.Embed(
            title="⚖️ Item Comparison",
            description=f"*\"Let's see... old junk vs new junk. Riveting.\"*",
            color=COLORS['info']
        )
        
        # Compare stats
        new_stats = item_data.get('stats', {})
        old_stats = equipped_data.get('stats', {})
        
        # Get all unique stat names
        all_stats = set(new_stats.keys()) | set(old_stats.keys())
        
        new_column = f"**{item_name}**\n"
        old_column = f"**{equipped_name}** (Current)\n"
        
        for stat in sorted(all_stats):
            new_value = new_stats.get(stat, 0)
            old_value = old_stats.get(stat, 0)
            
            stat_display = stat.replace('_', ' ').title()
            
            if new_value > old_value:
                new_column += f"✅ {stat_display}: {new_value} (+{new_value - old_value})\n"
                old_column += f"❌ {stat_display}: {old_value}\n"
            elif new_value < old_value:
                new_column += f"❌ {stat_display}: {new_value}\n"
                old_column += f"✅ {stat_display}: {old_value} (+{old_value - new_value})\n"
            else:
                new_column += f"⚪ {stat_display}: {new_value}\n"
                old_column += f"⚪ {stat_display}: {old_value}\n"
        
        embed.add_field(name="📊 New Item", value=new_column, inline=True)
        embed.add_field(name="📊 Equipped Item", value=old_column, inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self.inventory_view)

class SellItemButton(discord.ui.Button):
    """Sell the selected item."""
    
    def __init__(self, inventory_view):
        item_data = ITEMS.get(inventory_view.selected_item, {})
        sell_price = item_data.get('sell_price', 10)
        
        super().__init__(
            label=f"Sell ({format_number(sell_price)} Gold)",
            emoji="💰",
            style=discord.ButtonStyle.danger,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        # Create confirmation view
        confirm_view = SellConfirmationView(self.inventory_view, self.inventory_view.selected_item)
        
        item_data = ITEMS.get(self.inventory_view.selected_item, {})
        item_name = item_data.get('name', self.inventory_view.selected_item.replace('_', ' ').title())
        sell_price = item_data.get('sell_price', 10)
        
        embed = discord.Embed(
            title="💰 Confirm Sale",
            description=f"*\"You sure you want to get rid of this {item_name}? I mean, it's not cheese, so I don't really care, but...\"*\n\n"
                       f"**Item:** {item_name}\n"
                       f"**Sale Price:** {format_number(sell_price)} Gold\n\n"
                       f"Are you sure you want to sell this item?",
            color=COLORS['warning']
        )
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)

class BackToInventoryButton(discord.ui.Button):
    """Return to main inventory view."""
    
    def __init__(self, inventory_view):
        super().__init__(
            label="Back to Inventory",
            emoji="🔙",
            style=discord.ButtonStyle.secondary,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        self.inventory_view.in_inspection_mode = False
        self.inventory_view.selected_item = None
        self.inventory_view.update_components()
        
        embed = self.inventory_view.create_main_inventory_embed()
        await interaction.response.edit_message(embed=embed, view=self.inventory_view)

class SellConfirmationView(discord.ui.View):
    """Confirmation dialog for selling items."""
    
    def __init__(self, inventory_view, item_key):
        super().__init__(timeout=60)
        self.inventory_view = inventory_view
        self.item_key = item_key
    
    @discord.ui.button(label="Confirm Sale", emoji="✅", style=discord.ButtonStyle.danger)
    async def confirm_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        player_data = self.inventory_view.player_data
        inventory = player_data.get('inventory', {})
        
        # Check if item still exists
        if inventory.get(self.item_key, 0) <= 0:
            await interaction.response.send_message("Item no longer in inventory!", ephemeral=True)
            return
        
        # Process sale
        item_data = ITEMS.get(self.item_key, {})
        item_name = item_data.get('name', self.item_key.replace('_', ' ').title())
        sell_price = item_data.get('sell_price', 10)
        
        # Remove item
        if inventory[self.item_key] > 1:
            inventory[self.item_key] -= 1
        else:
            inventory.pop(self.item_key, None)
        
        # Add gold
        player_data['gold'] = player_data.get('gold', 0) + sell_price
        
        # Save changes
        self.inventory_view.rpg_core.save_player_data(self.inventory_view.user_id, player_data)
        
        # Plagg's response
        if 'cheese' in self.item_key.lower():
            response = "WHAT?! You sold CHEESE?! This is a travesty! A crime against all that is holy and delicious!"
        else:
            responses = [
                "Good riddance. More space for cheese.",
                "Finally got rid of some junk. Now let's find some actual food.",
                "Sold it for pocket change. Probably could've bought half a cheese wheel with that.",
                "One person's trash is another person's... also trash. But hey, gold is gold."
            ]
            import random
            response = random.choice(responses)
        
        embed = discord.Embed(
            title="💰 Item Sold!",
            description=f"*\"{response}\"*\n\n"
                       f"**{item_name}** has been sold for **{format_number(sell_price)} Gold**!",
            color=COLORS['success']
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.inventory_view.user_id:
            await interaction.response.send_message("Not your inventory!", ephemeral=True)
            return
        
        # Return to item inspection
        embed = self.inventory_view.create_item_inspection_embed(self.item_key)
        self.inventory_view.update_components()
        await interaction.response.edit_message(embed=embed, view=self.inventory_view)

class RPGInventoryManager(commands.Cog):
    """Plagg's reluctant inventory management system."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="inventory", aliases=["inv", "bag", "items"])
    async def inventory_command(self, ctx):
        """Open Plagg's inventory management interface."""
        if not is_module_enabled("rpg", ctx.guild.id):
            return
        
        rpg_core = self.bot.get_cog('RPGCore')
        if not rpg_core:
            await ctx.send("❌ RPG system not loaded.")
            return
        
        player_data = rpg_core.get_player_data(ctx.author.id)
        if not player_data:
            embed = create_embed(
                "No Character", 
                "You need to create a character first! Use `$startrpg` to begin your adventure.",
                COLORS['error']
            )
            await ctx.send(embed=embed)
            return
        
        # Create inventory view
        view = InventoryView(ctx.author.id, rpg_core)
        if not view.player_data:
            await ctx.send("❌ Error loading player data.")
            return
        
        embed = view.create_main_inventory_embed()
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name="equip")
    async def quick_equip(self, ctx, *, item_name: str = None):
        """Quickly equip an item by name."""
        if not is_module_enabled("rpg", ctx.guild.id):
            return
        
        if not item_name:
            await ctx.send("Please specify an item to equip! Example: `$equip iron sword`")
            return
        
        rpg_core = self.bot.get_cog('RPGCore')
        if not rpg_core:
            await ctx.send("❌ RPG system not loaded.")
            return
        
        player_data = rpg_core.get_player_data(ctx.author.id)
        if not player_data:
            await ctx.send("❌ Create a character first with `$startrpg`!")
            return
        
        # Find item in inventory
        inventory = player_data.get('inventory', {})
        item_key = None
        
        # Search by partial name
        item_name_lower = item_name.lower()
        for key in inventory:
            item_data = ITEMS.get(key, {})
            display_name = item_data.get('name', key.replace('_', ' ')).lower()
            if item_name_lower in display_name or item_name_lower in key.lower():
                item_key = key
                break
        
        if not item_key or inventory.get(item_key, 0) <= 0:
            await ctx.send(f"❌ You don't have '{item_name}' in your inventory!")
            return
        
        # Check if equippable
        item_data = ITEMS.get(item_key, {})
        item_type = item_data.get('type', '').lower()
        
        equipment_slots = {
            'weapon': 'weapon', 'sword': 'weapon', 'bow': 'weapon', 'staff': 'weapon',
            'helmet': 'helmet', 'chestplate': 'chestplate', 'armor': 'chestplate',
            'boots': 'boots', 'accessory': 'accessory', 'ring': 'ring', 
            'necklace': 'necklace', 'kwami_artifact': 'kwami_artifact'
        }
        
        slot = equipment_slots.get(item_type)
        if not slot:
            await ctx.send(f"❌ '{item_name}' cannot be equipped!")
            return
        
        # Perform equipment
        equipment = player_data.get('equipment', {})
        
        # Remove from inventory
        if inventory[item_key] > 1:
            inventory[item_key] -= 1
        else:
            inventory.pop(item_key, None)
        
        # Handle old equipment
        old_item = equipment.get(slot)
        if old_item:
            inventory[old_item] = inventory.get(old_item, 0) + 1
        
        # Equip new item
        equipment[slot] = item_key
        
        # Save
        player_data['equipment'] = equipment
        player_data['inventory'] = inventory
        rpg_core.save_player_data(ctx.author.id, player_data)
        
        item_display_name = item_data.get('name', item_key.replace('_', ' ').title())
        
        embed = discord.Embed(
            title="✅ Quick Equip Success!",
            description=f"*\"Fine, {item_display_name} is now equipped. You look... marginally less pathetic.\"*",
            color=COLORS['success']
        )
        
        if old_item:
            old_data = ITEMS.get(old_item, {})
            old_name = old_data.get('name', old_item.replace('_', ' ').title())
            embed.add_field(
                name="🔄 Replaced Item",
                value=f"**{old_name}** returned to inventory",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @commands.command(name="use")
    async def quick_use(self, ctx, *, item_name: str = None):
        """Quickly use a consumable item by name."""
        if not is_module_enabled("rpg", ctx.guild.id):
            return
        
        if not item_name:
            await ctx.send("Please specify an item to use! Example: `$use health potion`")
            return
        
        rpg_core = self.bot.get_cog('RPGCore')
        if not rpg_core:
            await ctx.send("❌ RPG system not loaded.")
            return
        
        player_data = rpg_core.get_player_data(ctx.author.id)
        if not player_data:
            await ctx.send("❌ Create a character first with `$startrpg`!")
            return
        
        # Find item in inventory
        inventory = player_data.get('inventory', {})
        item_key = None
        
        # Search by partial name
        item_name_lower = item_name.lower()
        for key in inventory:
            item_data = ITEMS.get(key, {})
            display_name = item_data.get('name', key.replace('_', ' ')).lower()
            if item_name_lower in display_name or item_name_lower in key.lower():
                item_key = key
                break
        
        if not item_key or inventory.get(item_key, 0) <= 0:
            await ctx.send(f"❌ You don't have '{item_name}' in your inventory!")
            return
        
        # Check if usable
        item_data = ITEMS.get(item_key, {})
        item_type = item_data.get('type', '').lower()
        
        if item_type not in ['consumable', 'potion', 'food', 'cheese']:
            await ctx.send(f"❌ '{item_name}' cannot be used!")
            return
        
        # Process item effects
        effect_result = self.process_item_effect(item_key, item_data, player_data)
        
        # Remove item from inventory
        if inventory[item_key] > 1:
            inventory[item_key] -= 1
        else:
            inventory.pop(item_key, None)
        
        # Save changes
        rpg_core.save_player_data(ctx.author.id, player_data)
        
        item_display_name = item_data.get('name', item_key.replace('_', ' ').title())
        
        embed = discord.Embed(
            title="🧪 Item Used!",
            description=f"**{item_display_name}** has been consumed!\n\n{effect_result}",
            color=COLORS['success']
        )
        
        await ctx.send(embed=embed)
    
    def process_item_effect(self, item_key, item_data, player_data):
        """Process the effects of using an item."""
        effect_type = item_data.get('effect_type')
        resources = player_data.get('resources', {})
        
        if 'cheese' in item_key.lower():
            # Special cheese handling
            hp_heal = item_data.get('heal_amount', 50)
            resources['hp'] = min(resources.get('max_hp', 100), resources.get('hp', 100) + hp_heal)
            return f"*\"NOW WE'RE TALKING! That cheese was absolutely divine! +{hp_heal} HP restored!\"*"
        
        elif effect_type == 'heal':
            heal_amount = item_data.get('heal_amount', 25)
            resources['hp'] = min(resources.get('max_hp', 100), resources.get('hp', 100) + heal_amount)
            return f"*\"Tastes awful, but I guess it worked. +{heal_amount} HP restored.\"*"
        
        elif effect_type == 'mana':
            mana_amount = item_data.get('mana_amount', 20)
            resources['mana'] = min(resources.get('max_mana', 50), resources.get('mana', 50) + mana_amount)
            return f"*\"Magical and boring. +{mana_amount} Mana restored.\"*"
        
        elif effect_type == 'buff':
            # Handle temporary buffs (would need a buff system)
            return f"*\"I suppose you feel slightly more capable now. For a few minutes.\"*"
        
        else:
            return f"*\"You consumed it. Something probably happened. I wasn't paying attention.\"*"

async def setup(bot):
    await bot.add_cog(RPGInventoryManager(bot))
