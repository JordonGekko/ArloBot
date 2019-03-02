from discord.ext import commands
import traceback
import sys


class Errors:

    def __init__(self, client):
        self.client = client

    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command"""
        error = getattr(error, 'original', error)

        if isinstance(error, commands.CommandNotFound):
            print(str(error))
            return

        elif isinstance(error, commands.DisabledCommand):
            print(str(error))
            await ctx.send(f'{ctx.command} has been disabled.')
            return

        elif isinstance(error, commands.NoPrivateMessage):
            print(str(error))
            try:
                return await ctx.author.send(f'{ctx.command} can not be used in Private Messages.')
            except Exception as e:
                print(e)
                pass
            return

        elif isinstance(error, commands.NotOwner):
            print(str(error))
            await ctx.send("This command can only be used by the owner of the bot.")
            return

        elif isinstance(error, commands.MissingPermissions):
            print(str(error))
            perms = '\n'.join([f"**{x}**" for x in error.missing_perms])
            await ctx.send(f"You are missing the required permissions to use this command:\n{perms}")
            return

        else:
            print(f'Ignoring exception in command {ctx.command}:')
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await ctx.send(f"```{type(error)} : {error}```")


def setup(client):
    client.add_cog(Errors(client))
