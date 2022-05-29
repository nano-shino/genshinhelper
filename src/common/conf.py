import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("BOT_TOKEN")

if not DISCORD_BOT_TOKEN:
    raise RuntimeError("Bot token is not present")

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

PIXIV_REFRESH_TOKEN = os.getenv("PIXIV_REFRESH_TOKEN", "")
PIXIV_CHANNEL_ID = os.getenv("PIXIV_CHANNEL_ID", "")
PIXIV_BLOCKED_TAGS = list(
    filter(None, os.getenv("PIXIV_BLOCKED_TAGS", "").split(","))
)
