import logging
import re
from datetime import datetime, timezone, timedelta
import discord
import toml
from discord.ext import commands

from Util.notice_identity import format_stable_id_display_tag


from Util.util_seoultechJob import *
from Util.util_seoultechITM import *
from Util.util_seoultechJanghak import *
from Util.util_seoultechContest import *

from Util.util_seoultechNotice import *


class ReactionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.save_emojis = bot.settings["DISCORD"]["EMOJIS"]["SAVE"]

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        guild = self.bot.get_guild(payload.guild_id)
        channel = self.bot.get_channel(payload.channel_id)
        log_channel = self.bot.get_channel(self.bot.settings["DISCORD"]["CHANNEL_ID"]["LOG"])
        if not guild or not channel:
            return

        user = guild.get_member(payload.user_id)
        if user.bot or payload.emoji.name not in self.save_emojis:
            return

        try:
            msg = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            await log_channel.send(f"[{now}]|Failed_to_fetch_message|msg_id={payload.message_id}")
            return

        # 1) 텍스트가 있으면 content로만 전송
        if msg.content:
            try:
                await user.send(content=msg.content)
            except discord.Forbidden:
                await channel.send(f"{user.mention}, DM을 열어주세요.")
                await log_channel.send(f"[{now}]|DM_forbidden|user={user.name}({user.id})")
                return

        # 2) 임베드가 있으면 embed 키워드 인자로만 전송 (positional arg 금지!)
        elif msg.embeds:
            for embed in msg.embeds:
                try:
                    await user.send(embed=self._sanitize_embed_for_dm(embed))
                except discord.Forbidden:
                    await channel.send(f"{user.mention}, DM을 열어주세요.")
                    await log_channel.send(f"[{now}]|DM_forbidden|user={user.name}({user.id})")
                    return

        # 3) 저장 완료 로그
        await log_channel.send(f"[{now}]|Saved_message|user={user.name}({user.id})|msg_id={msg.id}")

    @commands.command(name="check")
    async def check(self, ctx, website: str = "N0"):
        """!check [itm|janghak|job|contest|...] — 수동으로 최신 공지를 가져옵니다."""
        if website == "N0":
            await ctx.reply(
                "**사용 가능한 웹사이트**:\n"
                "`!check itm` — Seoultech ITM\n"
                "`!check janghak` — Seoultech Scholarship\n"
                "`!check job` — Seoultech Job\n"
                "`!check contest` — Seoultech Contest\n"
                "`!check notice` — Seoultech Notice\n"
            )
            return

        # 설정 로드
        cfg = toml.load(self.bot.settings_path)
        newest = cfg["CLIENT"]["NEWEST_POST"]
        save_emoji = cfg["DISCORD"]["EMOJIS"]["SAVE"][0]
        log_channel = self.bot.get_channel(self.bot.channel_ids["LOG"])
        now = datetime.now(timezone(timedelta(hours=9)))

        dispatch = {
            "itm": (newest["seoultechITM"], get_newest_content_seoultechITM),
            "janghak": (newest["seoultechJanghak"], get_newest_content_seoultechJanghak),
            "job": (newest["seoultechJob"], get_newest_content_seoultechJob),
            "contest": (newest["seoultechContest"], get_newest_content_seoultechContest),
            "notice" : (newest["seoultechNotice"], get_newest_content_seoultechNotice),
        }

        if website not in dispatch:
            return await ctx.reply(f"`{website}` 은(는) 지원하지 않는 옵션입니다.")

        post_info, fn = dispatch[website]
        await fn(
            id=post_info["ID"],
            url=post_info["URL"],
            target_channel=ctx.channel,
            log_channel=log_channel,
            current_time=now,
            save_emoji=save_emoji
        )

    def _sanitize_embed_for_dm(self, embed: discord.Embed) -> discord.Embed:
        copied = embed.copy()
        copied.title = self._format_legacy_stable_id_title(copied.title)
        return copied

    def _format_legacy_stable_id_title(self, title: str | None) -> str | None:
        if not title:
            return title

        match = re.match(r"^\[(bidx|qidx|profboardidx):([^\]]+)\](.*)$", title)
        if not match:
            return title

        stable_id = f"{match.group(1)}:{match.group(2)}"
        display_tag = format_stable_id_display_tag(stable_id, is_major_notice=False)
        return f"[{display_tag}]{match.group(3)}"
