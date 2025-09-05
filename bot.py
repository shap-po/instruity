import asyncio
import logging
import os
import discord
from discord.ext import commands
from discord.utils import setup_logging

from cogs import MusicCog

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger()
setup_logging()  # setup discord.py's default logger


class Instruity(commands.Bot):
    def __init__(
        self,
        token: str,
        speciality: str = None,
        **kwargs,
    ):
        super().__init__(**{
            'command_prefix': '!',  # required by discord.py but not used
            'intents': discord.Intents.default(),
            'help_command': None,
            **kwargs
        })
        self.token = token
        self.speciality = speciality
        self.logger = logger  # fallback logger, will be replaced in on_ready when bot's name is known

        hidden = os.environ.get('HIDDEN', '').lower() in ('1', 'true', 'yes', 'y', 'on')
        if hidden:
            self.status = discord.Status.invisible

    async def wrapped_connect(self):
        await self.add_cog(MusicCog(self))
        await self.login(self.token)
        try:
            await self.connect()
        except Exception as e:
            await self.close()

    async def on_ready(self):
        self.logger = logging.getLogger(f'bot:{self.user.name}')  # set logger to bot's name
        self.logger.info(f'Logged in as {self.user.name}')

        await self.tree.sync()


def main():
    tokens = os.environ.get('TOKENS') or os.environ.get('TOKEN')
    specialities = os.environ.get('SPECIALITIES') or os.environ.get('SPECIALITY')
    if not tokens:
        try:
            # left in for backwards compatibility, .env is the preferred method
            with open('tokens.txt', 'r') as f:
                tokens = f.read()
        except FileNotFoundError:
            logger.error(
                'Tokens not found. Either set the TOKENS environment variable or create a .env file with the TOKENS variable.')
            exit(1)
    tokens = tokens.split()

    if specialities:
        specialities = specialities.split()
        if len(specialities) != len(tokens):
            logger.warning('Specialities and tokens are not the same length. Specialities will be ignored.')
            specialities = None
        else:
            specialities = [
                s if s.lower() not in ('none', 'null', 'nil', '-') else None
                for s in specialities
            ]
    if not specialities:
        specialities = [None] * len(tokens)

    bots = [Instruity(token, speciality) for token, speciality in zip(tokens, specialities)]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        asyncio.gather(
            *[bot.wrapped_connect() for bot in bots]
        )
    )
    loop.run_forever()


if __name__ == '__main__':
    main()
