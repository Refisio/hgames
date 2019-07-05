"""
The cycle goes as follows:
Bloodbath
Day/Night
Day/Night
Day/Night
. . .

- This cycle can be represented in code with a simple `while` loop and turn counter.
- Random events permeate the loop, such as battlefield changes and feasts, allowing for more spice to the gameplay loop.
- - Default probability for these events should start at 1%, and increase to up to 20% as each night passes.


TODOS:
- Game Logic. Half of it is there. Just need the gameplay loop.
- Documentation.
"""
from pathlib import Path
from random import choice as singlechoice, choices, sample

import discord
from discord.ext.commands import Cog, check, cooldown, group
from discord.ext.commands.cooldowns import BucketType


# Should this inherit from discord.Member?
# Probably not, too much junk that we don't need from it.
# Move this out of the cog file
class Player:
    """
    A standard player class.

    This will allow for the creation of a new player for each game,
    taking from discord.Member without directly subclassing it.
    This will also allow us to make custom players for "Bench players",
    players who do not actually exist for the purpose of filling slots.
    """

    def __init__(self, player_id: int, player_name, image: str = None):
        self._id = player_id
        self.name = player_name
        self.image = image
        self.team = 0

    def __str__(self):
        return f'Name: {self.name}, ID: {self._id}'


# Maybe randomize them when self._started is flipped in start_game().
# Needs to be async-ified
# Needs to be moved out of cogs file.
class GameState:
    """
    Our general gamestate object.

    This will track the game state of the games that are played within servers,
    as well as providing the functionality for each game. This also allows unfinished
    games to die off when the bot process dies without having to try to recreate it.
    Makes no sense of users to not just recreate the game.
    """

    def __init__(self, game_maker, guild, events, max_pc):
        self._started = False
        self._creator = game_maker
        self.day = 0
        self.daytime = True
        self.guild = guild  # a guild object, for iteration purposes
        self.max_pc = max_pc
        self.players = []
        self.teams = []
        self.events = self.execute_event(events)

    def _make_teams(self):
        def chunk(l, n):
            for i in range(0, len(l), n):
                yield (set(l[i:i + n]))

        teams = []
        players = sample(self.players)
        for player_group in chunk(players, 2):
            teams.append(player_group)
        self.teams = sample(teams)
        return

    def _rest_random_players(self):
        imported_players = choices(self._id.members, k=self.max_pc - len(self.players))
        for player in imported_players:
            if player in self.players:
                new_player = singlechoice(self._id.members)
                self.players.append(new_player)
                continue
            new_player = Player(player.id, str(player), player.avatar_url)
            self.add_player(new_player)
        return

    def add_player(self, player: Player):
        self.players.append(player)

    def advance_days(self):
        self.daytime = not self.daytime
        if self.daytime:
            self.day += 1

    def calc_feast(self):
        feast_chance = self.day * 5
        feast_choice = choices(['feast', self.daytime], weights=[feast_chance, 100 - feast_chance], k=1)[0]
        if not isinstance(feast_choice, str):
            feast_choice = 'day' if self.daytime else 'night'
        return feast_choice

    def calc_fatality(self):
        fatality_chance = self.day * 10
        return choices(['f', 'nf'], weights=[fatality_chance, 100 - fatality_chance], k=1)[0]

    def get_players(self):
        """Debugging function"""
        return [str(player) for player in self.players]

    def is_started(self):
        return self._started

    def start_game(self):
        if not len(self.players) == self.max_pc:
            self._rest_random_players()
        self._started = True

    # this takes too long to execute, and will only get more time-consuming
    def execute_event(self, events):
        if self.day == 0 and self.daytime:
            daytime = 'bb'
        else:
            daytime = self.calc_feast()
        players = self.players.copy()
        fatal = 'f'  # self.calc_fatality()
        possible_events = [event for event in events[daytime][fatal] if event['tributes'] <= len(players)]
        if not possible_events:
            return
        event = singlechoice(possible_events).copy()
        tributes = sample(players, event['tributes'])
        for key in event:
            if isinstance(event[key], str):
                event[key] = event[key].format(*tributes)
            elif isinstance(event[key], list):
                for x, key2 in enumerate(event[key]):
                    event[key][x] = key2.format(*tributes)
        print(f'Tributes: {tributes}', f'Players left: {players}', f'Event: {event}', sep='\n', end='\n\n')
        return event


# Checks for commands pertaining to game existance
def has_game():
    def pred(ctx):
        cog = ctx.bot.get_cog('HGames')
        return ctx.guild.id in cog.games

    return check(pred)


def has_no_game():
    def pred(ctx):
        cog = ctx.bot.get_cog('HGames')
        return ctx.guild.id not in cog.games

    return check(pred)


# Checks for commands check if games are started.
def game_started():
    def pred(ctx):
        cog = ctx.bot.get_cog('HGames')
        return cog.games[ctx.guild.id].is_started()

    return check(pred)


def game_not_started():
    def pred(ctx):
        cog = ctx.bot.get_cog('HGames')
        return not cog.games[ctx.guild.id].is_started()

    return check(pred)


class HGames(Cog):
    """
    The Hunger Games cog.

    Responsible for the user interface of the GameState.
    """

    def __init__(self, bot):
        self.bot = bot
        self.games = {}
        self.texts = {}
        for txt_file in Path('.').glob('*.json'):
            with txt_file.open() as my_file:
                self.texts[txt_file.stem] = my_file.readlines()

    @group(name='hgames')
    async def _hgames(self, ctx):
        """
        The overarching group command for the Hunger Games cog.

        Does nothing outside of allowing access to the other commands in the cog.
        """
        if ctx.invoked_subcommand:
            return
        await ctx.send_help(ctx.command)  # This should be more of a help message

    @has_no_game()
    @_hgames.command(name='newgame')
    async def _hgames_newgame(self, ctx, player_count=24):
        """
        Creates a new Hunger Game for the server the command is issued in. If one exists, the function returns normally.
        """
        self.games[ctx.guild.id] = GameState(ctx.author, ctx.guild, self.texts, player_count)
        return await ctx.send('Game successfully created.')

    @has_game()
    @cooldown(1, 30.0, BucketType.guild)
    @_hgames.command()
    async def check_members(self, ctx):
        """A debugging command that should be fleshed out later."""
        await ctx.send('\n'.join(self.games[ctx.guild.id].get_players()))

    @game_not_started()
    @has_game()
    @_hgames.command(name='volunteer')
    async def _hgames_volunteer(self, ctx, player_name=None, player_image=None, volunteer: discord.Member = None):
        """
        Allows for users to sign themselves up for the Hunger Games.

        Users will be placed into their own Player class, which will then be added to the gamestate.
        Users may volunteer others, but this should probably not be advertised.
        That should probably also be locked behind a permission, or by a role. Make sure to delete this last part later.
        """

        if not volunteer:
            volunteer = ctx.author
        player_name = player_name or str(volunteer)
        if not player_image:
            if ctx.message.attachments:
                image_url = ctx.message.attachments[0].url
                if image_url[-4:] in ['.png', '.jpg', 'jpeg']:
                    player_image = image_url
            else:
                player_image = volunteer.avatar_url_as(format='png', size=1024)
        player = Player(volunteer.id, player_name, image=player_image)
        self.games[ctx.guild.id].add_player(player)

    @game_not_started()
    @has_game()
    @_hgames.command(name='startgame')
    async def _hgames_startgame(self, ctx):
        self.games[ctx.guild.id].start_game()
        # start background loop for specific game here, if possible
        # self.tasks[GUILD] = self.bot.create_task(run_game_func()), if possible
        await ctx.send('Game started!')

    # definitely need a game host role, at least.
    @game_started()
    @has_game()
    @_hgames.command(name='continue')
    async def _hgames_continuegame(self, ctx):
        """
        Allows the Hunger Game to continue.

        Should probably make this a background task as well, for automation purposes.
        3 minutes/180 seconds per round, allowing for game hosts to continue before then. Maybe add time to GameState.
        /shrug
        Do it manually for now. Who cares about manual aggrovation?
        """
        pass


def setup(bot):
    bot.add_cog(HGames(bot))
