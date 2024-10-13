from src.get_info import get_response_seoultechITM, Post
from src.discord_bot import InitialBot
import discord
from datetime import datetime, timezone, timedelta
from discord.ext import tasks
import sys
import os
import toml


initialized_bot = InitialBot()
bot = initialized_bot.bot

DISCORD_TOKEN = initialized_bot.token
CHANNEL_IDS = initialized_bot.channel_id
urls = initialized_bot.urls

@bot.event
async def on_ready():
    sys.stdout.write('Login...\n')
    sys.stdout.write(f'Login bot: {bot.user}\n')
    sys.stdout.write(f'{bot.user}에 로그인하였습니다.\n')
    sys.stdout.write(f'ID: {bot.user.name}\n')
    guild = discord.utils.get(bot.guilds, id=initialized_bot.guild_id)
    if guild is None:
        sys.stdout.write("Bot is not connected to the specified guild.")
        return

    sys.stdout.write(f"Channel ID LIST: {initialized_bot.channel_id}\n")
    main_channel = bot.get_channel(initialized_bot.channel_id["MAIN"])
    log_channel = bot.get_channel(initialized_bot.channel_id["LOG"])

    if main_channel is None or log_channel is None:
        sys.stdout.write("Channel not found. Please check the channel IDs and ensure the bot has all access to it.")
        return
    else:
        sys.stdout.write(f"Found channel: Main:{main_channel.name} / Log:{log_channel.name}\n")

    await bot.change_presence(status=discord.Status.online, activity=discord.Game('Intellij로 개발'))

    embed = discord.Embed(title="ITM notificator has been initialized.",
                          description="Be PREPARED!",
                          color=discord.Colour.from_rgb(0, 0, 128))
    embed.set_author(name='ITM_NOTI')
    embed.set_footer(text="seoultech ITM")

    await main_channel.send(embed=embed)

    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst)
    await log_channel.send(f"##---|{current_time}|---**The_notification_bot_was_initialized**---## ")

    noti_checker.start(main_channel=main_channel, log_channel=log_channel)

@tasks.loop(hours=1)
async def noti_checker(main_channel, log_channel):
    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst)
    setting_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'res', 'config.toml'))
    with open(setting_path, 'r') as f:
        settings_toml = toml.load(f)

    current_newest_post = settings_toml["CLIENT"]["NEWEST_POST"]
    new_post, posts = get_response_seoultechITM()

    # If there is no new notification on the ITM website
    if new_post.id == current_newest_post["ID"]:
        await log_channel.send(f"##---|{current_time}|---**There_is_nothing_new_on_the_website**---## ")

    else:
        posts = sorted(posts, key=lambda x : x.date, reverse=False)
        for post in posts:
            if datetime.strptime(current_newest_post["DATE"], "%Y-%m-%d") <= datetime.strptime(post.date, "%Y-%m-%d") and not current_newest_post["ID"] == post.id:
                # If the newest post which was just published is newer than the prior new post
                embed = discord.Embed(title=f"[{post.id}] {post.title}...",
                                      description=f"Link: {post.link}",
                                      color=discord.Colour.from_rgb(0, 0, 128))

                embed.set_author(name='Seoultech ITM')
                embed.set_footer(text=f"New Notification by ITM")


                await main_channel.send(embed=embed)

                await log_channel.send(f"##---**{current_time}**---The_latest_notification_has_been_updated_['{current_newest_post["ID"]}'->'{post.id}']---## ")
                update_newest_post(post)
                current_newest_post = {"ID": post.id, "DATE": post.date}

def update_newest_post(post: Post):

    setting_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'res', 'config.toml'))

    with open(setting_path, 'r') as f:
        settings_toml = toml.load(f)
    settings_toml["CLIENT"]["NEWEST_POST"]["ID"] = post.id
    settings_toml["CLIENT"]["NEWEST_POST"]["DATE"] = post.date

    with open(setting_path, 'w') as f:
        toml.dump(settings_toml, f)
        f.close()

# Run the bot
if __name__ == "__main__":
    try:
        bot.run(initialized_bot.token)

    except discord.errors.LoginFailure as e:
        print("Improper token has been passed.")