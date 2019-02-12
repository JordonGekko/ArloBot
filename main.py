from discord.ext import commands
import os
import database as db

version = "1.0"
TOKEN = os.environ.get('DISCORD_TOKEN')

client = commands.Bot(command_prefix="-")
extensions = ["roles", "moderation", "errors"]

database = db.Database()


@client.event
async def on_ready():
    print("Bot is ready")

if __name__ == "__main__":
    for extension in extensions:
        try:
            client.load_extension(extension)
            print(f"{extension} loaded successfully")
        except Exception as error:
            print(f"{extension} loading failed [{error}]")

    client.run(TOKEN)
