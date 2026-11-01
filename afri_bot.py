import os
import sys
import io
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

# Afri-Network Support server configuration
GUILD_ID = 1566400095425925204

# Channels
TICKET_PANEL_CHANNEL_ID = 1566406130471534753  # 🎫〡create-ticket
TRANSCRIPTS_CHANNEL_ID = 1566406092572069909  # 📜〡transcripts
TICKET_PINGS_CHANNEL_ID = 1566406089115697173  # 🔔〡ticket-pings

# Categories
TICKET_CATEGORY_ID = 1566406128173060138  # 🎫〡support

# Roles
STAFF_ROLE_ID = 1566410488374493395  # Staff
OWNER_ROLE_ID = 1566409705222574122  # Owner
MANAGER_ROLE_ID = 1566410433609343147  # Manager
ADMIN_PLUS_ROLE_ID = 1566410435207634954  # Admin [+]
ADMIN_MINUS_ROLE_ID = 1566410442262183986  # Admin [-]
MOD_PLUS_ROLE_ID = 1566410449929379851  # Moderator [+]
MOD_MINUS_ROLE_ID = 1566410455834951743  # Moderator [-]

# Ticket categories with their associated roles
TICKET_CATEGORIES = {
    "vpn_support": {
        "name": "VPN Support",
        "emoji": "🌐",
        "description": "Click on this option to create a ticket",
        "roles": [ADMIN_PLUS_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID],
    },
    "support": {
        "name": "Support",
        "emoji": "🔖",
        "description": "Click on this option to create a ticket",
        "roles": [STAFF_ROLE_ID],
    },
    "punishment_appeal": {
        "name": "Punishment Appeal",
        "emoji": "🏳️",
        "description": "Click on this option to create a ticket",
        "roles": [MOD_PLUS_ROLE_ID, ADMIN_MINUS_ROLE_ID, ADMIN_PLUS_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID],
    },
    "report_player": {
        "name": "Report Player",
        "emoji": "❗",
        "description": "Click on this option to create a ticket",
        "roles": [STAFF_ROLE_ID],
    },
    "report_staff": {
        "name": "Report a Staff",
        "emoji": "🔧",
        "description": "Report a Staff Member",
        "roles": [ADMIN_PLUS_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID],
    },
}

# Ticket storage
TICKETS_FILE = "afri_tickets.json"
OWNER_TOPIC_PREFIX = "ticket-owner:"

# Staff permissions for ticket channels
STAFF_PERMISSIONS = {
    "view_channel": True,
    "send_messages": True,
    "read_message_history": True,
    "attach_files": True,
    "embed_links": True,
    "add_reactions": True,
    "manage_messages": True,
}

# User permissions for ticket channels
USER_PERMISSIONS = {
    "view_channel": True,
    "send_messages": True,
    "read_message_history": True,
    "attach_files": True,
    "embed_links": True,
    "add_reactions": True,
}

# Close reasons
CLOSE_REASONS = {
    "completed": "Completed",
    "no_response": "No response",
    "resolved": "Resolved",
    "other": "Other",
}

# Intents
intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
GUILD = discord.Object(id=GUILD_ID)


# ==================== Storage ====================

def load_tickets() -> dict:
    """Load tickets from JSON file."""
    try:
        with open(TICKETS_FILE, "r", encoding="utf-8") as f:
            import json
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_tickets(data: dict) -> None:
    """Save tickets to JSON file."""
    import json
    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_ticket(channel_id: int) -> dict:
    """Get ticket data for a channel."""
    return load_tickets().get(str(channel_id), {})


def save_ticket(channel_id: int, data: dict) -> None:
    """Save ticket data for a channel."""
    tickets = load_tickets()
    tickets[str(channel_id)] = data
    save_tickets(tickets)


def delete_ticket(channel_id: int) -> None:
    """Delete ticket data for a channel."""
    tickets = load_tickets()
    tickets.pop(str(channel_id), None)
    save_tickets(tickets)


# ==================== Helper Functions ====================

def is_ticket_channel(channel) -> bool:
    """Check if a channel is a ticket channel."""
    return isinstance(channel, discord.TextChannel) and (channel.topic or "").startswith(OWNER_TOPIC_PREFIX)


def is_staff(member: discord.Member) -> bool:
    """Check if a member is staff."""
    if member.guild_permissions.manage_channels:
        return True
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


def can_close(member: discord.Member, channel) -> bool:
    """Check if a member can close the ticket."""
    if not is_ticket_channel(channel):
        return False
    if is_staff(member):
        return True
    return channel.topic == f"{OWNER_TOPIC_PREFIX}{member.id}"


# ==================== Ticket Panel View ====================

class TicketPanelView(discord.ui.View):
    """View for the ticket panel with a category dropdown."""
    
    def __init__(self):
        super().__init__(timeout=None)
        
        # Build select options from TICKET_CATEGORIES
        options = []
        for key, cat in TICKET_CATEGORIES.items():
            options.append(
                discord.SelectOption(
                    label=cat["name"],
                    value=key,
                    description=cat["description"],
                    emoji=cat["emoji"],
                )
            )
        
        self.select = discord.ui.Select(
            placeholder="Select a category",
            custom_id="afri_ticket_category",
            options=options,
        )
        self.select.callback = self.on_category_select
        self.add_item(self.select)
    
    async def on_category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        category_key = select.values[0]
        await open_ticket(interaction, category_key)


class TicketCloseView(discord.ui.View):
    """View inside ticket channels with close button."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="Close Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="afri_ticket_close"
    )
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not can_close(interaction.user, interaction.channel):
            await interaction.response.send_message(
                "🚫 You cannot close this ticket.", ephemeral=True
            )
            return
        await prompt_close(interaction)


class TicketCloseConfirmView(discord.ui.View):
    """View for confirming ticket closure with reason."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.select(
        placeholder="Select close reason",
        custom_id="afri_ticket_reason",
        options=[
            discord.SelectOption(label="✅ Resolved", value="resolved", description="Issue has been resolved"),
            discord.SelectOption(label="✅ Completed", value="completed", description="Request completed"),
            discord.SelectOption(label="🔇 No Response", value="no_response", description="User stopped responding"),
            discord.SelectOption(label="📝 Other", value="other", description="Other reason"),
        ],
    )
    async def reason_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        await close_ticket(interaction, select.values[0])
    
    @discord.ui.button(
        label="Cancel",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
        custom_id="afri_ticket_cancel"
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Close cancelled.", view=None)


# ==================== Ticket Functions ====================

async def open_ticket(interaction: discord.Interaction, category_key: str) -> None:
    """Create a new ticket for the user with the selected category."""
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    
    # Get category info
    cat_info = TICKET_CATEGORIES.get(category_key)
    if cat_info is None:
        await interaction.followup.send("❌ Invalid ticket category.", ephemeral=True)
        return
    
    if not guild.me.guild_permissions.manage_channels:
        await interaction.followup.send(
            "🚫 The bot is missing the **Manage Channels** permission.", ephemeral=True
        )
        return
    
    # Check if user already has an open ticket
    owner_topic = f"{OWNER_TOPIC_PREFIX}{interaction.user.id}"
    existing = next((c for c in guild.text_channels if c.topic == owner_topic), None)
    if existing is not None:
        await interaction.followup.send(
            f"⚠️ You already have an open ticket: {existing.mention}\n\n"
            "Please close it first to open a new one.",
            ephemeral=True,
        )
        return
    
    # Get the roles for this category
    category_roles = []
    for role_id in cat_info["roles"]:
        role = guild.get_role(role_id)
        if role:
            category_roles.append(role)
    
    # Create permission overwrites
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(**USER_PERMISSIONS),
        guild.me: discord.PermissionOverwrite(**STAFF_PERMISSIONS),
    }
    
    # Add category-specific role permissions
    for role in category_roles:
        overwrites[role] = discord.PermissionOverwrite(**STAFF_PERMISSIONS)
    
    # Get category
    category = guild.get_channel(TICKET_CATEGORY_ID)
    
    # Create safe channel name
    safe_name = "".join(
        ch for ch in interaction.user.name.lower() if ch.isalnum() or ch in "-_"
    ).strip("-_") or str(interaction.user.id)
    
    # Create ticket channel name with category prefix
    cat_prefix = category_key.replace("_", "-")
    channel_name = f"{cat_prefix}-{safe_name}"[:95]
    
    # Create ticket channel
    try:
        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            topic=owner_topic,
            overwrites=overwrites,
            reason=f"Ticket opened by {interaction.user}",
        )
    except discord.HTTPException as e:
        print(f"Failed to create ticket channel: {e}")
        await interaction.followup.send(
            "❌ Failed to create ticket channel. Please try again.", ephemeral=True
        )
        return
    
    # Build role mentions
    role_mentions = " ".join(role.mention for role in category_roles)
    
    # Send header message
    embed = discord.Embed(
        title=f"{cat_info['emoji']} {cat_info['name']}",
        color=0x5865F2,
        description=(
            f"Hello {interaction.user.mention}!\n\n"
            f"**Category:** {cat_info['name']}\n\n"
            "Please describe your issue or question below:\n"
            "• **What** problem are you experiencing?\n"
            "• **When** did it start?\n"
            "• **Any error messages** or screenshots?\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💬 A staff member will be with you shortly."
        ),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"Ticket owner: {interaction.user}", icon_url=interaction.user.display_avatar.url)
    
    # Build allowed mentions list
    mention_role_ids = [role.id for role in category_roles]
    
    try:
        await channel.send(
            content=f"{interaction.user.mention}{role_mentions if role_mentions else ''}",
            embed=embed,
            view=TicketCloseView(),
            allowed_mentions=discord.AllowedMentions(users=[interaction.user], roles=mention_role_ids),
        )
    except discord.HTTPException as e:
        print(f"Failed to send header: {e}")
        try:
            await channel.delete(reason="Ticket setup failed")
        except discord.HTTPException:
            pass
        await interaction.followup.send(
            "❌ Failed to set up ticket. Please try again.", ephemeral=True
        )
        return
    
    # Notify staff in pings channel
    pings_channel = guild.get_channel(TICKET_PINGS_CHANNEL_ID)
    if pings_channel and isinstance(pings_channel, discord.TextChannel):
        notify_embed = discord.Embed(
            title=f"🔔 New {cat_info['name']} Ticket",
            color=0xFEE75C,
            description=(
                f"**User:** {interaction.user} (<@{interaction.user.id}>)\n"
                f"**Category:** {cat_info['name']}\n"
                f"**Ticket:** {channel.mention}\n\n"
                "Please check and respond promptly."
            ),
            timestamp=datetime.now(timezone.utc)
        )
        try:
            await pings_channel.send(embed=notify_embed)
        except discord.HTTPException as e:
            print(f"Failed to notify staff: {e}")
    
    # Save ticket data
    save_ticket(channel.id, {
        "owner_id": interaction.user.id,
        "created_at": time.time(),
        "status": "open",
        "category": category_key,
    })
    
    await interaction.followup.send(
        f"✅ Your ticket is ready: {channel.mention}", ephemeral=True
    )


async def prompt_close(interaction: discord.Interaction) -> None:
    """Show the close confirmation view."""
    embed = discord.Embed(
        title="🔒 Close Ticket",
        color=0xED4245,
        description=(
            "Are you sure you want to close this ticket?\n\n"
            "Select a reason below to confirm.\n\n"
            "📝 *A transcript will be saved.*"
        ),
    )
    await interaction.response.send_message(embed=embed, view=TicketCloseConfirmView())


async def close_ticket(interaction: discord.Interaction, reason: str) -> None:
    """Close the ticket and save transcript."""
    if not can_close(interaction.user, interaction.channel):
        await interaction.response.send_message(
            "🚫 You cannot close this ticket.", ephemeral=True
        )
        return
    
    await interaction.response.edit_message(content="🔒 Closing ticket...", view=None)
    
    channel = interaction.channel
    meta = get_ticket(channel.id)
    
    # Build transcript
    transcript = await build_transcript(channel, str(interaction.user), reason)
    
    # Send transcript to transcripts channel
    transcripts_channel = channel.guild.get_channel(TRANSCRIPTS_CHANNEL_ID)
    if transcripts_channel and isinstance(transcripts_channel, discord.TextChannel):
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            color=0xED4245,
            description=(
                f"**Channel:** `#{channel.name}`\n"
                f"**Opened by:** <@{meta.get('owner_id', 'unknown')}>\n"
                f"**Closed by:** {interaction.user}\n"
                f"**Reason:** {CLOSE_REASONS.get(reason, reason)}"
            ),
            timestamp=datetime.now(timezone.utc)
        )
        try:
            await transcripts_channel.send(
                embed=embed,
                file=discord.File(io.BytesIO(transcript.encode("utf-8")), filename=f"ticket-{channel.name}.txt"),
            )
        except discord.HTTPException as e:
            print(f"Failed to send transcript: {e}")
    
    # Send transcript to ticket owner
    owner = channel.guild.get_member(meta.get("owner_id"))
    if owner:
        try:
            await owner.send(
                embed=embed,
                file=discord.File(io.BytesIO(transcript.encode("utf-8")), filename=f"ticket-{channel.name}.txt"),
            )
        except discord.HTTPException:
            pass
    
    # Delete ticket data and channel
    delete_ticket(channel.id)
    try:
        await channel.delete(reason=f"Ticket closed by {interaction.user} ({reason})")
    except discord.HTTPException as e:
        print(f"Failed to delete ticket channel: {e}")


async def build_transcript(channel, closed_by: str, reason: str) -> str:
    """Build a transcript of the ticket conversation."""
    meta = get_ticket(channel.id)
    opened = meta.get("created_at")
    opened_at = (
        datetime.fromtimestamp(opened, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if opened
        else "unknown"
    )
    
    lines = [
        f"Ticket: #{channel.name}",
        f"Opened: {opened_at}",
        f"Owner: {meta.get('owner_id', 'unknown')}",
        f"Closed by: {closed_by}",
        f"Reason: {CLOSE_REASONS.get(reason, reason)}",
        "",
        "-" * 60,
        "",
    ]
    
    async for message in channel.history(limit=500, oldest_first=True):
        body = message.content or ""
        for attachment in message.attachments:
            body += f"\n[attachment] {attachment.url}"
        stamp = message.created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{stamp}] {message.author}: {body}".rstrip())
        lines.append("")
    
    return "\n".join(lines)


# ==================== Commands ====================

@tree.command(name="setup-ticket-panel", description="Post the ticket panel in the create-ticket channel", guild=GUILD)
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_ticket_panel(interaction: discord.Interaction) -> None:
    """Set up the ticket panel message."""
    guild = interaction.guild
    channel = client.get_channel(TICKET_PANEL_CHANNEL_ID)
    if channel is None:
        try:
            channel = await client.fetch_channel(TICKET_PANEL_CHANNEL_ID)
        except discord.HTTPException:
            channel = None
    
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message(
            "Ticket panel channel not found. Check the configuration.",
            ephemeral=True,
        )
        return
    
    embed = discord.Embed(
        title="Create a ticket",
        color=0x5865F2,
        description=(
            "Please click on the button below to create a support ticket."
        ),
    )
    if guild.icon:
        embed.set_author(name="Afri-Network Support", icon_url=guild.icon.url)
    
    await channel.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message(
        f"✅ Ticket panel posted in {channel.mention}.", ephemeral=True
    )


# ==================== Button Handlers ====================

@client.event
async def on_interaction(interaction: discord.Interaction):
    """Handle button and select interactions."""
    if not isinstance(interaction, discord.ComponentInteraction):
        return
    
    custom_id = interaction.data.get("custom_id", "")
    
    if custom_id == "afri_ticket_category":
        # Dropdown select for ticket category - handled by TicketPanelView callback
        pass
    elif custom_id == "afri_ticket_close":
        if not can_close(interaction.user, interaction.channel):
            await interaction.response.send_message(
                "🚫 You cannot close this ticket.", ephemeral=True
            )
            return
        await prompt_close(interaction)
    elif custom_id == "afri_ticket_cancel":
        await interaction.response.edit_message(content="❌ Close cancelled.", view=None)
    elif custom_id == "afri_ticket_reason":
        # Close reason select - handled by TicketCloseConfirmView callback
        pass


# ==================== Bot Ready ====================

@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print(f"Bot is ready!")
    
    # Sync commands
    try:
        synced = await tree.sync(guild=GUILD)
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


# Run the bot
# On Render, use the web server keep-alive; locally, run directly
try:
    import web_server
    web_server.keep_alive()
    client.run(TOKEN)
except ImportError:
    client.run(TOKEN)
