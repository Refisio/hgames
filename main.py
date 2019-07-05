import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from os import environ
from pathlib import Path

from discord.ext.commands import Bot


bot = Bot(command_prefix='%')


@bot.event
async def on_ready():
    print('READY TO GO.')


for cog in Path('./cogs').glob('*.py'):
    print(f'LOADING COG FROM {cog}')
    bot.load_extension(f'cogs.{cog.stem}')

bot.run(environ.get('BOTTOKEN'))
