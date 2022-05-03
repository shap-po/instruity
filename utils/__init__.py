from discord import Member
import discord


async def smart_send(interaction: discord.Interaction, *args, **kwargs) -> None:
    """Send message or edit origin."""
    # if interaction is a button - send message which will be deleted after 10 seconds
    if interaction.data.get('custom_id'):
        await interaction.channel.send(*args, **kwargs, delete_after=10)
        if not interaction.response._responded:
            try:
                await interaction.response.send_message()
            except:
                # response will raise an error because of empty message, but it's ok
                pass
        return

    if interaction.response._responded:
        await interaction.followup.send(*args, **kwargs)
    else:
        await interaction.response.send_message(*args, **kwargs)


def is_admin(member: Member) -> bool:
    return member.guild_permissions.administrator
