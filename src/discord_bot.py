import discord
from discord.ext import commands
import os
import toml
from os.path import abspath


class InitialBot:
    def __init__(self):
        script_path = os.path.dirname(__file__)
        setting_path = abspath(os.path.join(script_path, '..', 'res', 'config.toml'))

        with open(setting_path, 'r') as f:
            settings_toml = toml.load(f)

        # Set default intent for discord client
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        #  Bot token, SERVER ID, CHANNEL ID
        self.script_path = script_path
        self.setting_path = setting_path
        self.token = settings_toml["DISCORD"]["TOKEN"]
        self.guild_id = settings_toml["DISCORD"]["GUILD_ID"]
        self.channel_id = settings_toml["DISCORD"]["CHANNEL_ID"]
        self.command_prefix = settings_toml["DISCORD"]["COMMAND_PREFIX"]
        self.urls = settings_toml["CLIENT"]["URLS"]
        self.newest_post = settings_toml["CLIENT"]["NEWEST_POST"]
        self.bot = commands.Bot(command_prefix=self.command_prefix, intents=intents)
