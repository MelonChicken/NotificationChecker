import os
import logging
import toml

import discord
from discord.ext import commands

from src.cogs.notifier import NotifierCog
from src.cogs.reaction import ReactionCog


class DiscordBot(commands.Bot):
    def __init__(self, settings: dict, settings_path: str):
        # Intents 초기화
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        intents.reactions = True

        super().__init__(
            command_prefix=settings["DISCORD"]["COMMAND_PREFIX"],
            intents=intents
        )

        # 설정 및 경로 속성 부착
        self.settings = settings
        self.settings_path = settings_path
        self.token = settings["DISCORD"]["TOKEN"]
        self.guild_id = settings["DISCORD"]["GUILD_ID"]
        self.channel_ids = settings["DISCORD"]["CHANNEL_ID"]
        self.urls = settings["CLIENT"]["URLS"]
        self.newest_post = settings["CLIENT"]["NEWEST_POST"]

    async def setup_hook(self):
        # Cog 등록은 setup_hook에서 비동기로 처리
        await self.add_cog(NotifierCog(self))
        await self.add_cog(ReactionCog(self))
        # 필요 시 슬래시 커맨드 동기화
        # await self.tree.sync()


def main():
    # 1) 설정 파일 경로 계산
    script_path = os.path.dirname(__file__)
    settings_path = os.path.abspath(
        os.path.join(script_path, '..', 'res', 'config.toml')
    )

    # 2) 설정 파일 로드
    settings = toml.load(settings_path)

    # 3) 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting bot")

    # 4) 봇 인스턴스 생성 및 실행
    bot = DiscordBot(settings, settings_path)
    try:
        bot.run(bot.token)
    except discord.errors.LoginFailure:
        logger.error("Invalid Discord token provided.")


if __name__ == "__main__":
    main()
