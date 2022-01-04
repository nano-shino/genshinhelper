from collections import defaultdict

import discord

from common import conf


_route_images = defaultdict(list)


def get_route_options(_):
    return list(_route_images.keys())


def get_route_images(resource: str):
    return _route_images[resource]


async def load_images(bot: discord.Bot):
    routes = defaultdict(list)
    route_count = 0

    channel = await bot.fetch_channel(conf.ROUTE_CHANNEL_ID)
    async for message in channel.history(limit=500):
        if message.attachments:
            for attachment in message.attachments:
                if 'image' in attachment.content_type:
                    components = attachment.filename.split(".")
                    material_name = components[0].replace("_", " ")
                    routes[material_name].append(((components[-1:1] or [1])[0], attachment.url))
                    route_count += 1

    _route_images.clear()
    for material in routes:
        _route_images[material] = [url for index, url in sorted(routes[material])]

    return route_count
