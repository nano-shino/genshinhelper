import asyncio
import base64
import io

import discord
from discord import Option
from discord.ext import commands
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from common import guild_level
from common.logging import logger


class UidHandler(commands.Cog):
    def __init__(self, bot: discord.Bot = None):
        self.bot = bot
        self.start_up = False

    @commands.slash_command(
        description="View in-game character info of a UID",
        guild_ids=guild_level.get_guild_ids(level=1),
    )
    async def uid(
            self,
            ctx: discord.ApplicationContext,
            uid: Option(str, "Genshin UID"),
    ):
        url = f"https://enka.shinshin.moe/u/{uid}"
        await ctx.respond(f"{url}")

        options = webdriver.ChromeOptions()
        options.headless = True
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), chrome_options=options)
        driver.get(url)

        wait = WebDriverWait(driver, 10)

        char_list = wait.until(expected_conditions.visibility_of_element_located((
            By.CLASS_NAME, "CharacterList")))

        found = False

        for i, avatar in enumerate(char_list.find_elements(by=By.CLASS_NAME, value="avatar")):
            logger.info(f"Exporting character {i}")
            avatar.click()
            await asyncio.sleep(2)

            button = wait.until(expected_conditions.visibility_of_element_located((
                By.XPATH, '//button[text()="Export image"]')))
            button.click()

            images = []
            for _ in range(5):
                images = driver.find_elements(by=By.TAG_NAME, value="img")
                count = 0
                for image in images:
                    if image.get_attribute("src").startswith("blob"):
                        count += 1
                if count == i + 1:
                    break

            await asyncio.sleep(1)

            for image in images[::-1]:
                src = image.get_attribute("src")
                if src.startswith("blob"):
                    base64data = driver.execute_script("""
                    let getImage = url => fetch(url)
                    .then(response => response.blob())
                    .then(blob => new Promise((resolve, reject) => {
                    const reader = new FileReader()
                    reader.onloadend = () => resolve(reader.result)
                    reader.onerror = reject
                    reader.readAsDataURL(blob)
                    }));
                    """ + f"return await getImage('{src}')")
                    png_bytes = base64.b64decode(base64data[base64data.find(",") + 1:])
                    file = discord.File(io.BytesIO(png_bytes), filename=f"{i}.png")
                    await ctx.send_followup(file=file)
                    found = True
                    break

        if not found:
            await ctx.edit(content="Cannot retrieve this UID")

        driver.close()
