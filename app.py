from src.Util.util_seoultechITM import NotificationCheckerSeoultechITM, get_newest_content_SeoultechITM
from src.Util.util_seoultechJanghak import NotificationCheckerSeoultechJanghak, get_newest_content_SeoultechJanghak
from src.Util.util_seoultechJob import NotificationCheckerSeoultechJob, get_newest_content_SeoultechJob
from src.Util.util_seoultechContest import NotificationCheckerSeoultechContest, get_newest_content_SeoultechContest
from src.discord_bot import InitialBot
import discord
from datetime import datetime, timezone, timedelta
from discord.ext import tasks
import sys
import asyncio
import toml

initialized_bot = InitialBot()
bot = initialized_bot.bot

DISCORD_TOKEN = initialized_bot.token
CHANNEL_IDS = initialized_bot.channel_id
urls = initialized_bot.urls

settings_path = initialized_bot.setting_path
settings_toml = toml.load(initialized_bot.setting_path)


@bot.event
async def on_ready():
    sys.stdout.write('Login...\n')
    sys.stdout.write(f'Login bot: {bot.user}\n')
    sys.stdout.write(f'{bot.user}에 로그인하였습니다.\n')
    sys.stdout.write(f'ID: {bot.user.name}\n')
    guild = discord.utils.get(bot.guilds, id=initialized_bot.guild_id)
    if guild is None:
        sys.stdout.write("Bot is not connected to the specified guild.")

    sys.stdout.write(f"Channel ID LIST: {initialized_bot.channel_id}\n")
    channels_dict = initialized_bot.channel_id

    main_channel = bot.get_channel(channels_dict["MAIN"])
    log_channel = bot.get_channel(channels_dict["LOG"])
    dev_channel = bot.get_channel(channels_dict["DEV"])
    # test_content_ITM = get_contentSeoultechITM(url="https://itm.seoultech.ac.kr/bachelor_of_information/notice/?do=view&profboardidx=0&bnum=1947&bidx=553738&cate=7&allboard=false&nowpage=1")
    # await dev_channel.send(f"{test_content_ITM}")


    if main_channel is None or log_channel is None:
        sys.stdout.write("Channel not found. Please check the channel IDs and ensure the bot has all access to it.")

    else:
        channel_names = {key: bot.get_channel(channels_dict[key]).name for key, value in channels_dict.items()}
        sys.stdout.write(f"Found channel: {channel_names}\n")

    await bot.change_presence(status=discord.Status.online, activity=discord.Game('Intellij로 개발'))

    if not settings_toml['DISCORD']['INITIALIZED_FLAG']:
        embed = discord.Embed(title="NotificationChecker has been initialized.",
                              description="Be PREPARED!",
                              color=discord.Colour.from_rgb(0, 0, 128))
        embed.set_author(name='NOTI_CHECK')
        embed.set_footer(text="MLC")

        await main_channel.send(embed=embed)

        kst = timezone(timedelta(hours=9))
        current_time = datetime.now(kst)
        await log_channel.send(f"##---|{current_time}|---**The_notification_bot_was_initialized**---## ")

        with open(initialized_bot.setting_path, "w") as f:
            settings_toml['DISCORD']['INITIALIZED_FLAG'] = True
            toml.dump(settings_toml, f)

    noti_checker.start(main_channel=main_channel, log_channel=log_channel)


@tasks.loop(hours=1)
async def noti_checker(main_channel, log_channel):
    seoultech_itm = NotificationCheckerSeoultechITM(settings_path=settings_path, settings_toml=settings_toml,
                                          main_channel=main_channel, log_channel=log_channel)

    seoultech_janghak = NotificationCheckerSeoultechJanghak(settings_path=settings_path, settings_toml=settings_toml,
                                                  main_channel=main_channel, log_channel=log_channel)

    seoultech_job = NotificationCheckerSeoultechJob(settings_path=settings_path, settings_toml=settings_toml,
                                                  main_channel=main_channel, log_channel=log_channel)

    seoultech_contest = NotificationCheckerSeoultechContest(settings_path=settings_path, settings_toml=settings_toml,
                                                            main_channel=main_channel, log_channel=log_channel)

    website_tasks = [seoultech_itm.check(), seoultech_janghak.check(), seoultech_job.check(), seoultech_contest.check()]

    results = await asyncio.gather(*website_tasks, return_exceptions=True)

    for task_id, result in enumerate(results, start=1):
        if result:
            sys.stdout.write(f"Task {task_id} result: {result}\n")
        else:
            sys.stdout.write(f"Task {task_id} did not complete successfully\n")


@tasks.loop(hours=settings_toml['DISCORD']['UPDATE_PERIOD'] * 24)
async def bot_update(dev_channel):
    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst)
    await dev_channel.send(f"[{current_time}]|Time_to_update_server\n- link: https://hub.weirdhost.xyz/server/5b031035")


@bot.command()
async def check(ctx, website="N0"):

    if website == "N0":
        await ctx.reply(f"[The following list is about websites and their commands that we are currently offer the service about.]\n\n"
                        f"command : website description with link\n"
                        f"1. itm : [Seoultech ITM Notification](https://itm.seoultech.ac.kr/bachelor_of_information/notice/)\n\n"
                        f"2. janghak : [Seoultech Scholarship Notification](https://www.seoultech.ac.kr/service/info/janghak/)\n\n"
                        f"3. job : [Seoultech Job Notification](https://www.seoultech.ac.kr/service/info/job/)\n\n"
                        f"4. contest : [Seoultech Job Notification](https://www.seoultech.ac.kr/service/board/rec/)\n\n")
    else:
        initialized_bot.sync_newest_posts()

        kst = timezone(timedelta(hours=9))
        current_time = datetime.now(kst)

        log_channel = bot.get_channel(initialized_bot.channel_id["LOG"])


        if website == "itm":

            newest_post = initialized_bot.newest_post["seoultechITM"]

            await get_newest_content_SeoultechITM(id=newest_post["ID"], target_channel=ctx.channel, log_channel=log_channel,
                                                  current_time=current_time,
                                                  url=newest_post["URL"])

        elif website == "janghak":

            newest_post = initialized_bot.newest_post["seoultechJanghak"]

            await get_newest_content_SeoultechJanghak(id=newest_post["ID"], target_channel=ctx.channel, log_channel=log_channel,
                                                      current_time=current_time,
                                                      url=newest_post["URL"])

        elif website == "job":

            newest_post = initialized_bot.newest_post["seoultechJob"]

            await get_newest_content_SeoultechJob(id=newest_post["ID"], target_channel=ctx.channel, log_channel=log_channel,
                                                      current_time=current_time,
                                                      url=newest_post["URL"])

        elif website == "contest":

            newest_post = initialized_bot.newest_post["seoultechContest"]

            await get_newest_content_SeoultechContest(id=newest_post["ID"], target_channel=ctx.channel, log_channel=log_channel,
                                                  current_time=current_time,
                                                  url=newest_post["URL"])


# Run the bot
if __name__ == "__main__":
    try:
        bot.run(initialized_bot.token)

    except discord.errors.LoginFailure as e:
        sys.stdout.write("Improper token has been passed.")
