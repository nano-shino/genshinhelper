import os

DISCORD_BOT_TOKEN = os.getenv("BOT_TOKEN", "")
IMAGE_HOSTING_CHANNEL_ID = int(os.getenv("IMAGE_HOSTING_CHANNEL_ID", "0"))
ROUTE_CHANNEL_IDS = list(
    map(int, filter(None, os.getenv("ROUTE_CHANNEL_IDS", "").split(",")))
)
NEWS_CHANNEL_IDS = list(
    map(int, filter(None, os.getenv("NEWS_CHANNEL_IDS", "").split(",")))
)
CODE_CHANNEL_IDS = list(
    map(int, filter(None, os.getenv("CODE_CHANNEL_IDS", "").split(",")))
)
