import discord
from discord import Option
from discord.ext import commands, pages

from common import guild_level, autocomplete
from interfaces.route_loader import get_route_options, get_route_images


class FarmRouteHandler(commands.Cog):
    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False

    @commands.slash_command(
        description="Finds a farming route for a resource",
        guild_ids=guild_level.get_guild_ids(level=1),
    )
    async def route(
        self,
        ctx,
        resource: Option(
            str,
            "Name of the resource like Sango Pearl",
            autocomplete=autocomplete.fuzzy_autocomplete(get_route_options),
        ),
        public: Option(
            bool,
            "Set the visibility to public instead of just you",
            required=False,
            default=False,
        ),
    ):
        await ctx.defer(ephemeral=not public)

        if not get_route_images(resource):
            await ctx.send_followup("No routes found")
            return

        embeds = []
        for image_url in get_route_images(resource):
            embed = discord.Embed(description=resource.capitalize())
            embed.set_image(url=image_url)
            embeds.append(embed)

        paginator = pages.Paginator(
            pages=embeds,
            show_disabled=True,
            show_indicator=True,
            author_check=False,
            timeout=60 * 60,
        )
        await paginator.respond(ctx.interaction)
