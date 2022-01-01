from collections import defaultdict

import discord
from discord import Option
from discord.ext import commands, pages

from common import guild_level, autocomplete, conf
from common.logging import logger

route_images = {}


async def get_route_options(_):
    return list(route_images.keys())


class FarmRouteHandler(commands.Cog):

    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False
        self.route_images = route_images

    @commands.Cog.listener()
    async def on_ready(self):

        if not self.start_up:
            routes = defaultdict(list)
            route_count = 0

            channel = await self.bot.fetch_channel(conf.ROUTE_CHANNEL_ID)
            async for message in channel.history(limit=200):
                if message.attachments:
                    for attachment in message.attachments:
                        if 'image' in attachment.content_type:
                            components = attachment.filename.split(".")
                            material_name = components[0].replace("_", " ")
                            routes[material_name].append(((components[-1:1] or [1])[0], attachment.url))
                            route_count += 1

            for material in routes:
                self.route_images[material] = [url for index, url in sorted(routes[material])]

            logger.info(f"Loaded {route_count} route images")
            self.start_up = True

    @commands.slash_command(
        description="Find a farming route for a resource",
        guild_ids=guild_level.get_guild_ids(level=1),
    )
    async def route(
            self,
            ctx,
            resource: Option(str, "Name of the resource like Sango Pearl",
                             autocomplete=autocomplete.fuzzy_autocomplete(get_route_options)),
            public: Option(bool, "Set the visibility to public instead of just you",
                           required=False, default=False)
    ):
        await ctx.defer(ephemeral=not public)

        if not self.route_images[resource]:
            await ctx.respond("No routes found")
            return

        embeds = []
        for image_url in route_images[resource]:
            embed = discord.Embed(description=resource.capitalize())
            embed.set_image(url=image_url)
            embeds.append(embed)

        paginator = pages.Paginator(pages=embeds, show_disabled=True, show_indicator=True, author_check=False)
        await paginator.respond(ctx)
