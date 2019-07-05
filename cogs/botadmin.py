from discord.ext.commands import Cog, group, command


class BotAdmin(Cog):

    pass


def setup(bot):
    bot.add_cog(BotAdmin())
