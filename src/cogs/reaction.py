import logging
from datetime import datetime, timezone, timedelta
import discord
import toml
from discord.ext import commands


from src.Util.util_seoultechJob import *
from src.Util.util_seoultechITM import *
from src.Util.util_seoultechJanghak import *
from src.Util.util_seoultechContest import *


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
        log_ch = self.bot.get_channel(self.bot.settings["DISCORD"]["CHANNEL_ID"]["LOG"])
        if not guild or not channel:
            return

        user = guild.get_member(payload.user_id)
        if user.bot or payload.emoji.name not in self.save_emojis:
            return

        try:
            msg = await channel.fetch_message(payload.message_id)
            # 콘텐츠 전송 로직 (텍스트/임베드 모두 handle)
            await user.send(msg.content or msg.embeds[0])
            await log_ch.send(f"[{now}]|Saved msg {msg.id} for {user.name}")
        except discord.Forbidden:
            await channel.send(f"{user.mention}, DM을 열어주세요.")
            await log_ch.send(f"[{now}]|DM forbidden for {user.name}")
        except Exception as e:
            await log_ch.send(f"[{now}]|Error in reaction handler: {e}")

    @commands.command(name="check")
    async def check(self, ctx, website: str = "N0"):
        """!check [itm|janghak|job|contest] — 수동으로 최신 공지를 가져옵니다."""
        if website == "N0":
            await ctx.reply(
                "**사용 가능한 웹사이트**:\n"
                "`!check itm` — Seoultech ITM\n"
                "`!check janghak` — Seoultech Scholarship\n"
                "`!check job` — Seoultech Job\n"
                "`!check contest` — Seoultech Contest\n"
            )
            return

        # 설정 로드
        cfg = toml.load(self.bot.settings_path)
        newest = cfg["CLIENT"]["NEWEST_POST"]
        save_emoji = cfg["DISCORD"]["EMOJIS"]["SAVE"][0]
        log_channel = self.bot.get_channel(self.bot.channel_ids["LOG"])
        now = datetime.now(timezone(timedelta(hours=9)))

        dispatch = {
            "itm": (newest["seoultechITM"], get_newest_content_SeoultechITM),
            "janghak": (newest["seoultechJanghak"], get_newest_content_seoultechJanghak),
            "job": (newest["seoultechJob"], get_newest_content_seoultechJob),
            "contest": (newest["seoultechContest"], get_newest_content_seoultechContest),
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