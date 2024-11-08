# Holly Bot

Holly is a Discord bot representing the ship mainframe of the ship "The Starlight Sleigh". It handles ranks of the crew (and their players), as well as the ship's inventory and other functions.

## Features

- Manage crew members and their ranks
- Handle cargo inventory
- Store and retrieve user messages
- Admin commands for managing the bot

## Commands

### Crew Management

- `/newmember` - Add a new crew member
- `/removemember` - Remove a crew member
- `/promote` - Promote a crew member
- `/demote` - Demote a crew member
- `/strike` - Strike a crew member
- `/resign_rank` - Resign from a rank
- `/member` - Get information about a crew member

### Cargo Management

- `/cargo` - Get information about the cargo
- `/addcargo` - Add an item to the cargo
- `/removecargo` - Remove an item from the cargo
- `/reloadcargo` - Reload the cargo data

### Message Management

- `/get_message` - Get a message by ID
- `/get_messages` - Get all messages by user ID

### Admin Commands

- `/reload` - Reload the crew data
- `/is_admin` - Check if the user is an admin

## Setup

1. Clone the repository.
2. Install the required dependencies.
3. Create a `token.priv` file with your Discord bot token.
4. Run the bot.

```sh
git clone <repository-url>
cd Holly
pip install -r requirements.txt
echo "YOUR_DISCORD_BOT_TOKEN" > token.priv
python main.py
```

## License

This project is not currently released under any standard license