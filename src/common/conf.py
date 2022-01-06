import os

DISCORD_BOT_TOKEN = os.getenv('BOT_TOKEN')
ROUTE_CHANNEL_IDS = list(map(int, os.getenv('ROUTE_CHANNEL_IDS').split(",")))
NEWS_CHANNEL_IDS = list(map(int, os.getenv('NEWS_CHANNEL_IDS').split(",")))
CODE_CHANNEL_IDS = list(map(int, os.getenv('CODE_CHANNEL_IDS').split(",")))
