import os

DISCORD_BOT_TOKEN = os.getenv('BOT_TOKEN')
DISCORD_GUILD_IDS = [int(x) for x in os.getenv('BOT_GUILD_IDS').split(",")]
