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

class CrewMember:
    def __init__(self, name, rank, player, strikes = 0): # Initialize a CrewMember object
        self.name = name
        self.rank = rank
        self.player = player # discord user id
        self.strikes = strikes # Strikes for the member
    
    def __str__(self): # String representation of a CrewMember object
        return f"{self.name} - {self.rank} - {self.player}"
    
    def __repr__(self): # Representation of a CrewMember object
        return f"{self.name} - {self.rank} - {self.player}"
    
    def __eq__(self, other): # Check if two CrewMember objects are equal
        return self.name == other.name and self.rank == other.rank and self.player == other.player
    
    def __hash__(self): # Hash a CrewMember object
        return hash((self.name, self.player))
        
    def promote(self, member_promoting): 
        # Check that the rank being promoted to is not higher than the rank of the member promoting
        if Ranks.index(member_promoting.rank) <= Ranks.index(self.rank):
            return False

        # If the member is already at the highest rank, they cannot be promoted
        if self.rank == "Admiral":
            return False

        # Determine the new rank for promotion
        newrank = Ranks[Ranks.index(self.rank) - 1]  # Move up one rank in the Ranks tuple

        # Make sure the new rank is not higher than the rank of the member promoting
        if Ranks.index(member_promoting.rank) <= Ranks.index(newrank):
            return False

        # Apply the new rank
        self.rank = newrank
        return True
    
    def demote(self, member_demoting):
        # Check that the rank of the member demoting is not lower than the rank of the member being demoted
        if Ranks.index(member_demoting.rank) >= Ranks.index(self.rank):
            return False

        # If the member is already at the lowest rank, they cannot be demoted
        if self.rank == "Crew":
            return False

        # Determine the new rank for demotion
        newrank = Ranks[Ranks.index(self.rank) + 1]  # Move down one rank in the Ranks tuple

        # Make sure the new rank is not lower than the rank of the member demoting
        if Ranks.index(member_demoting.rank) >= Ranks.index(newrank):
            return False

        # Apply the new rank
        self.rank = newrank
        return True


### This function is called when the bot is ready to start being used
@client.event
async def on_ready():
    await tree.sync()

    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game("Here to Serve!")
    )
    
    await load_crew_data()
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

        print(f"Stored message ID {msg_id} for user {user_id} ({user_display_name}): '{message}' at {timestamp}")

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

        if rows:
            message_str = ""
            for row in rows:
                message_str += f"Message ID {row[0]} at {row[1]}: '{row[4]}'\n"
            await interaction.response.send_message(message_str)
        else:
            await interaction.response.send_message(f"No messages found for user {user.id} ({user.display_name})")

async def load_crew_data():
    # Initialize crew members from file
    ranks_path = os.path.join("crew_data", "members.json")
    
    async with aiofiles.open(ranks_path, "r") as f:
        crew_data = await f.read()
    try:
        crew_data = json.loads(crew_data)
    except json.JSONDecodeError:
        # Crew is likely empty
        logger.warning("Crew members file is empty, if this is not expected, please check the file")
        crew_data = []

    global crew
    crew = set()

    for member in crew_data:
        crew.add(CrewMember(member["name"], member["rank"], member["player"], member["strikes"]))
        logger.info(f"Loaded crew member {member['name']} with rank {member['rank']} and player {member['player']} (Strikes: {member['strikes']})")

async def save_crew_data():
    ranks_path = os.path.join("crew_data", "members.json")

    crew_data = []

    for member in crew:
        crew_data.append({
            "name": member.name,
            "rank": member.rank,
            "player": member.player,
            "strikes": member.strikes
        })
    
    async with aiofiles.open(ranks_path, "w") as f:
        await f.write(json.dumps(crew_data, indent=4))
    
    logger.info("Crew data saved")

    # Optional backup with dill
    async with aiofiles.open(os.path.join("crew_data", "members.dill"), "wb") as f:
        await f.write(dill.dumps(crew))
    
    logger.info("Crew data backed up with dill")

async def get_member_by_name(name):
    for member in crew:
        if member.name == name:
            return member
    return None

async def get_member_by_player(player):
    for member in crew:
        if member.player == player:
            return member
    return None

async def get_members_by_rank(rank):
    members = set()
    for member in crew:
        if member.rank == rank:
            members.add(member)
    return members

async def new_member(name, rank, player):
    member = CrewMember(name, rank, player)
    crew.add(member)
    await save_crew_data()
    return member

async def remove_member(member):
    crew.remove(member)
    await save_crew_data()

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
    
    await interaction.response.send_message(f"Name: {member.name}\nRank: {member.rank}\nPlayer: {member.player}\nStrikes: {member.strikes}")

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
    
    await remove_member(member)
    await interaction.response.send_message(f"Member {name} removed")

@tree.command(name="promote", description="Promote a crew member")
async def promote(interaction, name: str):
    member_promoting = await get_member_by_player(interaction.user.id)
    member = await get_member_by_name(name)
    if member is None:
        await interaction.response.send_message("Member not found", ephemeral=True)
        return
    
    if not member.promote(member_promoting):
        await interaction.response.send_message("Member cannot be promoted. You may have not enough permissions or the member is already at the highest rank", ephemeral=True)
        return
    
    await save_crew_data()
    await interaction.response.send_message(f"Member {name} promoted to {member.rank}")

@tree.command(name="demote", description="Demote a crew member")
async def demote(interaction, name: str):
    member_demoting = await get_member_by_player(interaction.user.id)
    if not isinstance(member_demoting, CrewMember):
        await interaction.response.send_message("You do not have permission or you are not recognized as a valid member to perform this action", ephemeral=True)
        return

    member = await get_member_by_name(name)
    if not isinstance(member, CrewMember):
        await interaction.response.send_message("The specified member was not found", ephemeral=True)
        return

    if not member.demote(member_demoting):
        await interaction.response.send_message("Member cannot be demoted. You may have not enough permissions or the member is already at the lowest rank", ephemeral=True)
        return

    await save_crew_data()
    await interaction.response.send_message(f"Member {name} demoted to {member.rank}")

@tree.command(name="reload", description="Reload the crew data")
async def reload(interaction):
    if interaction.user.id != 262687596642041856: 
        await interaction.response.send_message("You do not have permission to reload the crew data", ephemeral=True)

    await load_crew_data()
    await interaction.response.send_message("Crew data reloaded")

@tree.command(name="strike", description="Strike a crew member")
async def strike(interaction, name: str):
    member_striking = await get_member_by_player(interaction.user.id)
    member = await get_member_by_name(name)

    if not isinstance(member_striking, CrewMember):
        await interaction.response.send_message("You do not have permission or you are not recognized as a valid member to perform this action", ephemeral=True)
        return
    
    if not isinstance(member, CrewMember):
        await interaction.response.send_message("Member not found", ephemeral=True)
        return

    # Check that the member striking is at least a Lieutenant and that the member being struck is lower than them
    if not member_striking.rank in ("Lieutenant", "Captain", "Commodore", "Admiral"):
        await interaction.response.send_message("You do not have permission to strike this member", ephemeral=True)
        return
    elif Ranks.index(member_striking.rank) <= Ranks.index(member.rank):
        await interaction.response.send_message("You do not have permission to strike this member", ephemeral=True)
        return

    if member is None:
        await interaction.response.send_message("Member not found", ephemeral=True)
        return
    
    member.strikes += 1
    await save_crew_data()
    await interaction.response.send_message(f"Member {name} now has {member.strikes} strikes")

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
    if not isinstance(member, CrewMember):
        await interaction.response.send_message("You are not recognized as a valid member to perform this action", ephemeral=True)
        return

    if member.rank == "Crew":
        await interaction.response.send_message("You are already at the lowest rank", ephemeral=True)
        return

    # Shift rank down by 1
    member.rank = Ranks[Ranks.index(member.rank) + 1]


    await save_crew_data()
    await interaction.response.send_message("Resigned from rank")


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

# Syntax for a lambda function:
# lambda arguments: expression
# Example:
# x = lambda a, b: a * b
# print(x(5, 6)) # Output: 30
# The lambda function above is equivalent to:
# def x(a, b):
#     return a * b

# advanced example:
# x = lambda a, b: a * b if a > 0 and b > 0 else 0
# print(x(5, 6)) # Output: 30

# The lambda function above is equivalent to:
# def x(a, b):
#     if a > 0 and b > 0:
#         return a * b