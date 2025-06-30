# src/cogs/notifier.py
import logging
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands, tasks

# 절대 경로로 refactor된 Checker 클래스 가져오기
from src.Util.util_seoultechJob import *
from src.Util.util_seoultechITM import *
from src.Util.util_seoultechJanghak import *
from src.Util.util_seoultechContest import *

CHECKER_CLASSES = [
    SeoultechITMChecker,
    SeoultechJanghakChecker,
    SeoultechJobChecker,
    SeoultechContestChecker,
]

class NotifierCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.settings
        self.logger = logging.getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self):
        # 채널 ID도 bot 속성에서 가져옵니다
        ids = self.bot.channel_ids
        self.main_channel = self.bot.get_channel(ids["DEV"])
        self.log_channel  = self.bot.get_channel(ids["LOG"])
        self.logger.info("NotifierCog ready; starting noti_task")
        self.noti_task.start()

    @tasks.loop(hours=1)
    async def noti_task(self):
        now = datetime.now(timezone(timedelta(hours=9)))
        for CheckerClass in CHECKER_CLASSES:
            checker = CheckerClass(
                settings_path=self.bot.settings_path,
                settings_toml=self.settings,
                main_channel=self.main_channel,
                log_channel=self.log_channel
            )
            try:
                # 여기가 실제로 각 서브클래스의 get_latest_posts를 호출합니다
                success = await checker.check()
                if success:
                    self.logger.info(f"{CheckerClass.__name__}: check() succeeded")
                else:
                    self.logger.warning(f"{CheckerClass.__name__}: check() returned False")
            except NotImplementedError:
                # 이 에러가 뜨면 get_latest_posts가 Override되지 않은 것
                self.logger.error(f"{CheckerClass.__name__} did not implement get_latest_posts()")
            except Exception:
                # 그 외 예외는 스택트레이스와 함께 기록
                self.logger.exception(f"Unexpected error in {CheckerClass.__name__}.check()")

    @noti_task.before_loop
    async def before_noti(self):
        # 봇이 준비될 때까지 대기
        await self.bot.wait_until_ready()
