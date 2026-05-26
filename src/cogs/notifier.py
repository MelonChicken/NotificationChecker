# src/cogs/notifier.py
import asyncio
import logging
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands, tasks

# 절대 경로로 refactor된 Checker 클래스 가져오기
from Util.util_seoultechJob import *
from Util.util_seoultechITM import *
from Util.util_seoultechJanghak import *
from Util.util_seoultechContest import *
from Util.util_seoultechNotice import *

from src.Util.util_seoultechNotice import SeoultechNoticeChecker
from api.notice_summary import generate_recent_notice_summary

CHECKER_CLASSES = [
    SeoultechITMChecker,
    SeoultechJanghakChecker,
    SeoultechJobChecker,
    SeoultechContestChecker,
    SeoultechNoticeChecker,
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
        self.main_channel = self.bot.get_channel(ids["MAIN"])
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

    @commands.command(name="summary")
    async def summary(self, ctx):
        try:
            summary_text, notice_count = await asyncio.to_thread(
                generate_recent_notice_summary,
                self.bot.settings_path,
            )
            for index, chunk in enumerate(self._split_message(summary_text)):
                if index == 0:
                    await ctx.reply(chunk)
                else:
                    await ctx.send(chunk)
            await self.log_channel.send(
                f"[{datetime.now(timezone(timedelta(hours=9)))}]|Summary_generated|count={notice_count}"
            )
        except Exception as e:
            self.logger.exception("Failed to generate summary")
            await ctx.reply("요약 생성 중 오류가 발생했습니다.")
            await self.log_channel.send(
                f"[{datetime.now(timezone(timedelta(hours=9)))}]|Summary_failed|{e}"
            )

    @noti_task.before_loop
    async def before_noti(self):
        # 봇이 준비될 때까지 대기
        await self.bot.wait_until_ready()

    def _split_message(self, text: str, limit: int = 1900):
        if len(text) <= limit:
            return [text]

        chunks = []
        remaining = text
        while len(remaining) > limit:
            split_at = remaining.rfind("\n", 0, limit)
            if split_at == -1:
                split_at = limit
            chunks.append(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip()
        if remaining:
            chunks.append(remaining)
        return chunks
