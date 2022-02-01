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

    files = []

    for route_channel_id in conf.ROUTE_CHANNEL_IDS:
        channel = await bot.fetch_channel(route_channel_id)
        async for message in channel.history(limit=500):
            if message.attachments:
                for attachment in message.attachments:
                    if "image" in attachment.content_type:
                        filename = attachment.filename.replace("_", " ")
                        files.append((filename, attachment.url))

    filename_lookup = {filename for filename, url in files}
    files.sort()

    for i, (filename, url) in enumerate(files):
        components = filename.rsplit(".", 2)

        if len(components) == 3:
            # Check if it's actually <name>.<idx>.png format
            if components[1].isdigit():
                idx = int(components[1])
                if idx == 1 and f"{components[0]}.2.{components[2]}" in filename_lookup:
                    components = [components[0], idx, url]
                elif idx > 1 and components[0] in routes:
                    components = [components[0], idx, url]

            if not type(components[1]) == int:
                components = ["".join(components[:2]), 1, url]
        else:
            components = [components[0], 1, url]

        material_name = components[0]
        routes[material_name].append(components[1:])
        route_count += 1

    _route_images.clear()
    for material in routes:
        _route_images[material] = [url for index, url in sorted(routes[material])]

    return route_count
