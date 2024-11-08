# This bot "holly" is a discord bot representing the ship mainframe of the ship "The Starlight Sleigh"
# It handles ranks of the crew (and their players), as well as the ship's inventory and other functions

import discord
from discord import app_commands
import logging
import dill
import os
import re
import asyncio
import aiofiles
from datetime import datetime, timedelta 
import json
import numpy as np
import aiosqlite

### Discord Bot Setup
needed_intents = discord.Intents.default()
needed_intents.message_content = True
needed_intents.members = True
client = discord.Client(intents=needed_intents)
tree = app_commands.CommandTree(client)


### Logging Setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
file_handler = logging.FileHandler('holly.log')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.addHandler(file_handler)

### Global Variables
# Ranks = Admiral > Commodore > Captain > Lieutenant > Ensign > Crew
Ranks = ("Admiral", "Commodore", "Captain", "Lieutenant", "Ensign", "Crew") # Ranks in order of highest to lowest stored as a tuple (immutable list)


### This function is called when the bot is ready to start being used
@client.event
async def on_ready():
    await tree.sync()

    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game("Here to Serve!")
    )
    
    await init_cew_db()
    await load_cargo()
    
    logger.info("Bot is ready to use")

# Function to store user messages in the database
async def store_user_message(conn, msg_id, user_id, user_display_name, message, timestamp):
    async with conn.cursor() as cursor:
        # Create a table if it doesn't exist
        await cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_messages (
            msg_id INTEGER PRIMARY KEY,           -- Message ID as the primary key
            timestamp TEXT NOT NULL,              -- Timestamp field
            user_id INTEGER NOT NULL,             -- User ID field
            user_display_name TEXT NOT NULL,      -- User display name field
            message TEXT NOT NULL                 -- Message text field
        )
        ''')
        await conn.commit()  # Commit the table creation

        # Insert the user message into the table
        await cursor.execute(
            "INSERT INTO user_messages (msg_id, timestamp, user_id, user_display_name, message) VALUES (?, ?, ?, ?, ?)",
            (msg_id, timestamp, user_id, user_display_name, message)
        )
        await conn.commit()  # Commit the insertion

        # print(f"Stored message ID {msg_id} for user {user_id} ({user_display_name}): '{message}' at {timestamp}")

# Function to get message by ID
async def get_message_by_id(conn, msg_id):
    async with conn.cursor() as cursor:
        # Query the database for the message with the given ID
        await cursor.execute("SELECT * FROM user_messages WHERE msg_id = ?", (msg_id,))
        row = await cursor.fetchone()

        if row:
            return row  # (msg_id, timestamp, user_id, user_display_name, message)
        else:
            return None

# Function to get all messages by user ID
async def get_messages_by_user_id(conn, user_id):
    async with conn.cursor() as cursor:
        # Query the database for all messages by the given user ID
        await cursor.execute("SELECT * FROM user_messages WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()

        return rows  # List of (msg_id, timestamp, user_id, user_display_name, message)

@client.event
async def on_message(message):
    # Avoid responding to messages from the bot itself
    if message.author == client.user:
        return

    db_path = os.path.join("msg_data", "usr_messages.db")
    async with aiosqlite.connect(db_path) as conn:
        timestamp = message.created_at
        formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Store the user message in the database
        await store_user_message(conn, message.id, message.author.id, message.author.display_name, message.content, formatted_timestamp)

@tree.command(name="get_message", description="Get a message by ID")
async def get_message(interaction, msg_id: int):
    db_path = os.path.join("msg_data", "usr_messages.db")
    async with aiosqlite.connect(db_path) as conn:
        row = await get_message_by_id(conn, msg_id)

        if row:
            await interaction.response.send_message(f"Message ID {msg_id} by user {row[2]} ({row[3]}) at {row[1]}: '{row[4]}'")
        else:
            await interaction.response.send_message(f"Message ID {msg_id} not found")

@tree.command(name="get_messages", description="Get all messages by user ID")
async def get_messages(interaction, user: discord.User):
    if interaction.user.id != 262687596642041856:
        await interaction.response.send_message("You do not have permission to get messages", ephemeral=True)
        return
    
    db_path = os.path.join("msg_data", "usr_messages.db")
    async with aiosqlite.connect(db_path) as conn:
        rows = await get_messages_by_user_id(conn, user.id)

        # If there are more than 10 messages, only send the last 10
        truncated = False
        if len(rows) > 10:
            rows = rows[-10:]
            truncated = True

        try:
            if rows:
                message_str = ""
                for row in rows:
                    message_str += f"Message ID {row[0]} at {row[1]}: '{row[4]}'\n"
                await interaction.response.send_message(message_str)
                if truncated:
                    await interaction.followup.send("Only the last 10 messages were shown. If you need more, please use the get_message command with the message ID")
            else:
                await interaction.response.send_message(f"No messages found for user {user.id} ({user.display_name})")
        except discord.errors.HTTPException as e:
            await interaction.response.send_message(f"The messages have too many characters to be displayed here. Please use the get_message command with the message ID")

async def init_cew_db():
    async with aiosqlite.connect("crew_data.db") as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS crew (
                name TEXT PRIMARY KEY,
                rank TEXT NOT NULL,
                player INTEGER NOT NULL,
                strikes INTEGER NOT NULL
            )
        ''')
        await db.commit()

async def get_member_by_name(name):
    async with aiosqlite.connect("crew_data.db") as db:
        async with db.execute("SELECT * FROM crew WHERE name = ?", (name,)) as cursor:
            return await cursor.fetchone()

async def get_member_by_player(player):
    async with aiosqlite.connect("crew_data.db") as db:
        async with db.execute("SELECT * FROM crew WHERE player = ?", (player,)) as cursor:
            return await cursor.fetchone()

async def get_members_by_rank(rank):
    async with aiosqlite.connect("crew_data.db") as db:
        async with db.execute("SELECT * FROM crew WHERE rank = ?", (rank,)) as cursor:
            return await cursor.fetchall()

async def new_member(name, rank, player):
    async with aiosqlite.connect("crew_data.db") as db:
        await db.execute('''
            INSERT INTO crew (name, rank, player, strikes) VALUES (?, ?, ?, 0)
        ''', (name, rank, player))
        await db.commit()

async def remove_member(name):
    async with aiosqlite.connect("crew_data.db") as db:
        await db.execute("DELETE FROM crew WHERE name = ?", (name,))
        await db.commit()

async def promote(member_name, member_promoting):
    member = await get_member_by_name(member_name)
    if not member:
        return False

    if Ranks.index(member_promoting[1]) <= Ranks.index(member[1]):
        return False

    if member[1] == "Admiral":
        return False

    newrank = Ranks[Ranks.index(member[1]) - 1]
    if Ranks.index(member_promoting[1]) <= Ranks.index(newrank):
        return False

    async with aiosqlite.connect("crew_data.db") as db:
        await db.execute("UPDATE crew SET rank = ? WHERE name = ?", (newrank, member_name))
        await db.commit()
    return True

async def demote(member_name, member_demoting):
    member = await get_member_by_name(member_name)
    if not member:
        return False

    if Ranks.index(member_demoting[1]) >= Ranks.index(member[1]):
        return False

    if member[1] == "Crew":
        return False

    newrank = Ranks[Ranks.index(member[1]) + 1]
    if Ranks.index(member_demoting[1]) >= Ranks.index(newrank):
        return False

    async with aiosqlite.connect("crew_data.db") as db:
        await db.execute("UPDATE crew SET rank = ? WHERE name = ?", (newrank, member_name))
        await db.commit()
    return True

@tree.command(name="member", description="Get information about a crew member")
async def member(interaction, name: str = "", id: str = "", user: discord.User = None):
    # If neither are provided, return an error
    if name == "" and id == "" and user is None:
        await interaction.response.send_message("Please provide a name, id or user", ephemeral=True)
        return
    elif name != "" and id != "": # TODO: Add a check for user too
        await interaction.response.send_message("Please only provide a name, id or user", ephemeral=True)
        return
    
    if user is not None:
        member = await get_member_by_player(user.id)
    elif name != "":
        member = await get_member_by_name(name)
    elif id != "":
        member = await get_member_by_player(id)
    else:
        member = None

    if member is None:
        await interaction.response.send_message("Member not found", ephemeral=True)
        return
    
    await interaction.response.send_message(f"Name: {member[0]}\nRank: {member[1]}\nPlayer: {member[2]}\nStrikes: {member[3]}")

@tree.command(name="newmember", description="Add a new crew member")
async def newmember(interaction, name: str, rank: str, player: discord.User):
    if interaction.user.id != 262687596642041856:
        await interaction.response.send_message("You do not have permission to add a member", ephemeral=True)
        return

    if await get_member_by_name(name) is not None:
        await interaction.response.send_message("Member already exists", ephemeral=True)
        return
    
    if await get_member_by_player(player.id) is not None:
        await interaction.response.send_message("Player already has a member", ephemeral=True)
        return
    
    if rank not in Ranks:
        await interaction.response.send_message("Invalid rank", ephemeral=True)
        return
    
    await new_member(name, rank, player.id)
    await interaction.response.send_message(f"Member {name} added with rank {rank} and player {player.id}")

@tree.command(name="removemember", description="Remove a crew member")
async def removemember(interaction, name: str):
    if interaction.user.id != 262687596642041856:
        await interaction.response.send_message("You do not have permission to remove a member", ephemeral=True)
        return
    member = await get_member_by_name(name)
    if member is None:
        await interaction.response.send_message("Member not found", ephemeral=True)
        return
    
    await remove_member(name)
    await interaction.response.send_message(f"Member {name} removed")

@tree.command(name="promote", description="Promote a crew member")
async def promote(interaction, name: str):
    member_promoting = await get_member_by_player(interaction.user.id)
    member = await get_member_by_name(name)
    if member is None:
        await interaction.response.send_message("Member not found", ephemeral=True)
        return
    
    if not await promote(name, member_promoting):
        await interaction.response.send_message("Member cannot be promoted. You may have not enough permissions or the member is already at the highest rank", ephemeral=True)
        return
    
    await interaction.response.send_message(f"Member {name} promoted to {member[1]}")

@tree.command(name="demote", description="Demote a crew member")
async def demote(interaction, name: str):
    member_demoting = await get_member_by_player(interaction.user.id)
    if not member_demoting:
        await interaction.response.send_message("You do not have permission or you are not recognized as a valid member to perform this action", ephemeral=True)
        return

    member = await get_member_by_name(name)
    if not member:
        await interaction.response.send_message("The specified member was not found", ephemeral=True)
        return

    if not await demote(name, member_demoting):
        await interaction.response.send_message("Member cannot be demoted. You may have not enough permissions or the member is already at the lowest rank", ephemeral=True)
        return

    await interaction.response.send_message(f"Member {name} demoted to {member[1]}")

@tree.command(name="strike", description="Strike a crew member")
async def strike(interaction, name: str):
    member_striking = await get_member_by_player(interaction.user.id)
    member = await get_member_by_name(name)

    if not member_striking:
        await interaction.response.send_message("You do not have permission or you are not recognized as a valid member to perform this action", ephemeral=True)
        return
    
    if not member:
        await interaction.response.send_message("Member not found", ephemeral=True)
        return

    if not member_striking[1] in ("Lieutenant", "Captain", "Commodore", "Admiral"):
        await interaction.response.send_message("You do not have permission to strike this member", ephemeral=True)
        return
    elif Ranks.index(member_striking[1]) <= Ranks.index(member[1]):
        await interaction.response.send_message("You do not have permission to strike this member", ephemeral=True)
        return

    async with aiosqlite.connect("crew_data.db") as db:
        await db.execute("UPDATE crew SET strikes = strikes + 1 WHERE name = ?", (name,))
        await db.commit()
    
    await interaction.response.send_message(f"Member {name} now has {member[3] + 1} strikes")


# Load cargo
async def load_cargo():
    # Initialize cargo from file
    cargo_path = os.path.join("cargo_data", "cargo.json")
    
    async with aiofiles.open(cargo_path, "r") as f:
        cargo_data = await f.read()
    try:
        cargo_data = json.loads(cargo_data)
    except json.JSONDecodeError:
        # Cargo is likely empty
        logger.warning("Cargo file is empty, if this is not expected, please check the file")
        cargo_data = []

    global cargo
    cargo = {}

    for item in cargo_data:
        cargo[item["name"]] = item["quantity"]
        logger.info(f"Loaded cargo {item['name']} with quantity {item['quantity']}")

async def save_cargo():
    cargo_path = os.path.join("cargo_data", "cargo.json")

    cargo_data = []

    for item in cargo:
        cargo_data.append({
            "name": item,
            "quantity": cargo[item]
        })
    
    async with aiofiles.open(cargo_path, "w") as f:
        await f.write(json.dumps(cargo_data, indent=4))
    
    logger.info("Cargo data saved")

@tree.command(name="cargo", description="Get information about the cargo")
async def cargo(interaction):
    cargo_str = ""
    for item in cargo:
        cargo_str += f"{item}: {cargo[item]}\n"
    await interaction.response.send_message(cargo_str)

@tree.command(name="addcargo", description="Add an item to the cargo")
async def addcargo(interaction, item: str, quantity: int):
    if interaction.user.id != 262687596642041856:
        await interaction.response.send_message("You do not have permission to add cargo", ephemeral=True)
        return

    if item in cargo:
        cargo[item] += quantity
    else:
        cargo[item] = quantity
    
    await save_cargo()
    await interaction.response.send_message(f"Added {quantity} of {item} to the cargo")

@tree.command(name="removecargo", description="Remove an item from the cargo")
async def removecargo(interaction, item: str, quantity: int):
    if interaction.user.id != 262687596642041856:
        await interaction.response.send_message("You do not have permission to remove cargo", ephemeral=True)
        return

    if item not in cargo:
        await interaction.response.send_message("Item not found in cargo", ephemeral=True)
        return
    
    if cargo[item] < quantity:
        await interaction.response.send_message("Not enough of the item in the cargo", ephemeral=True)
        return
    
    cargo[item] -= quantity
    await save_cargo()
    await interaction.response.send_message(f"Removed {quantity} of {item} from the cargo")

@tree.command(name="reloadcargo", description="Reload the cargo data")
async def reloadcargo(interaction):
    if interaction.user.id != 262687596642041856:
        await interaction.response.send_message("You do not have permission to reload the cargo data", ephemeral=True)

    await load_cargo()
    await interaction.response.send_message("Cargo data reloaded")

@tree.command(name="resign_rank", description="Resign from a rank")
async def resign_rank(interaction):
    member = await get_member_by_player(interaction.user.id)
    if not member:
        await interaction.response.send_message("You are not recognized as a valid member", ephemeral=True)
        return
    
    if member[1] == "Crew":
        await interaction.response.send_message("You are already at the lowest rank", ephemeral=True)
        return
    
    newrank = Ranks[Ranks.index(member[1]) + 1]

    async with aiosqlite.connect("crew_data.db") as db:
        await db.execute("UPDATE crew SET rank = ? WHERE player = ?", (newrank, interaction.user.id))
        await db.commit()
    
    await interaction.response.send_message(f"You have resigned from {member[1]} to {newrank}")


@tree.command(name="is_admin") # Use a lambda function to check if the user is an admin
async def is_admin(interaction):
    admins = [262687596642041856, 262687596642041856] # List of admin user ids

    await interaction.response.send_message("You are an admin" if interaction.user.id in admins else "You are not an admin")

if __name__ == "__main__":
    logger.info("Program started in main.py")

    if not os.path.exists("token.priv"): # Check if the token file exists
        logger.error("Token file not found")
        exit(1) # Exit the program using error code 1

    with open("token.priv", "r") as f:
        token = f.read().strip()
    
    client.run(token) # Run the bot with the token from the file
