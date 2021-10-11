from discord.ext import commands
from discord_slash import SlashContext, ComponentContext, cog_ext

from utils import smart_send
from utils.actions import *
from ext.music import MusicCog


class ActionsCog(commands.Cog):
    def __init__(self, music_cog: MusicCog):
        self.music_cog = music_cog

    @cog_ext.cog_slash(name='actions', description='Получить список быстрых действий')
    async def actions(self, ctx: SlashContext):
        await smart_send(ctx, 'Быстрые действия', components=full_actions)
        # await ctx.channel.send('Избранные треки и плейлисты', components=saved_actions)

    async def play_infinite(self, ctx: ComponentContext):
        """Enable infinite playlist mode and select playlist."""
        voice_client = self.music_cog.get_voice_client(ctx)
        if not await self.music_cog.ensure_voice_state(ctx, voice_client):
            return
        if not voice_client.voice:
            await self.music_cog.join.invoke(ctx)

        action = ctx.custom_id
        if action == voice_client.infinite_playlist:
            await smart_send(ctx, f'Плейлист "{action}" уже играет')
            return

        ac = 'Режим бесконечной музыки включен & ' if not voice_client.infinite_playlist else ''
        await smart_send(ctx, f'{ac}Выбран плейлист "{action}"')
        voice_client.infinite_playlist = action

        voice_client.infinite_queue.clear()
        await voice_client.random_infinite_song()
        await voice_client.random_infinite_song()
        if voice_client.current:
            if voice_client.current.infinite:
                voice_client.skip()
        else:
            await voice_client.queue.add(await voice_client.random_infinite_song(False))

    async def exit_infinite(self, ctx: ComponentContext):
        """Disable infinite playlist mode."""
        voice_client = self.music_cog.get_voice_client(ctx)
        if not await self.music_cog.ensure_voice_state(ctx, voice_client):
            return

        if voice_client.infinite_playlist:
            voice_client.infinite_playlist = None
            if voice_client.current:
                if voice_client.current.infinite:
                    voice_client.skip()
            voice_client.infinite_queue.clear()
            await smart_send(ctx, 'Режим бесконечной музыки выключен')
        else:
            await smart_send(ctx, 'Режим бесконечной музыки уже выключен')

    async def play_saved(self, ctx: ComponentContext):
        """Add saved song or playlist to queue"""
        voice_client = self.music_cog.get_voice_client(ctx)
        if not await self.music_cog.ensure_voice_state(ctx, voice_client):
            return

    '''async def update_actions(self, ctx: ComponentContext):
        await ctx.edit_origin(components=full_actions)'''


controls_list = {
    'pause':   Action(style=ButtonStyle.blue, emoji='⏯', function='pause'),
    'skip':    Action(style=ButtonStyle.blue, emoji='⏭', function='skip'),
    'stop':    Action(style=ButtonStyle.blue, emoji='⏹', function='stop'),
    'loop':    Action(style=ButtonStyle.blue, emoji='🔁', function='loop'),
    'shuffle': Action(style=ButtonStyle.blue, emoji='🔀', function='shuffle'),
    'now':     Action(style=ButtonStyle.blue, emoji='🎶', function='now'),
    'queue':   Action(style=ButtonStyle.blue, emoji='📃', function='queue'),
    'clear':   Action(style=ButtonStyle.blue, emoji='🧹', function='clear'),
}
infinite_action_list = {
    'spooky':   Action(emoji='👻', function='play_infinite'),
    'medieval': Action(emoji='🏰', function='play_infinite'),
    'forest':   Action(emoji='🌲', function='play_infinite'),
    'magical':  Action(emoji='✨', function='play_infinite'),
    'relaxing': Action(emoji='😊', function='play_infinite'),
    'epic':     Action(emoji='☠', function='play_infinite'),

    'exit':     Action(emoji='🚫', function='exit_infinite'),
}

saved_action_list = {
    'saved1':  Action(style=ButtonStyle.blue, emoji='1️⃣', function='play_saved'),
    'saved2':  Action(style=ButtonStyle.blue, emoji='2️⃣', function='play_saved'),
    'saved3':  Action(style=ButtonStyle.blue, emoji='3️⃣', function='play_saved'),
    'saved4':  Action(style=ButtonStyle.blue, emoji='4️⃣', function='play_saved'),
    'saved5':  Action(style=ButtonStyle.blue, emoji='5️⃣', function='play_saved'),

    'saved6':  Action(style=ButtonStyle.blue, emoji='6️⃣', function='play_saved'),
    'saved7':  Action(style=ButtonStyle.blue, emoji='7️⃣', function='play_saved'),
    'saved8':  Action(style=ButtonStyle.blue, emoji='8️⃣', function='play_saved'),
    'saved9':  Action(style=ButtonStyle.blue, emoji='9️⃣', function='play_saved'),
    'saved10': Action(style=ButtonStyle.blue, emoji='🔟', function='play_saved'),

    # 'update':    Action(style=ButtonStyle.gray, emoji='🔄', function='update_actions'),
}

music_actions_list = {**controls_list, **infinite_action_list}

saved_actions = create_actions(saved_action_list, 5)
controls_actions = create_actions(controls_list, 4)
full_actions = controls_actions + create_actions(infinite_action_list, 4)

opening_action_list = {'new_opening':  Action(
    style=ButtonStyle.gray, emoji='🔁', function='new_opening')}
opening_actions = create_actions(opening_action_list)
