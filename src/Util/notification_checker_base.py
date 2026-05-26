import traceback

import discord
import toml
import logging
from datetime import datetime, timezone, timedelta

from api.notice_summary import append_notice_history

class NotificationCheckerBase:
    def __init__(self, *, category_key: str, base_url: str,
                 settings_path: str, settings_toml: dict,
                 main_channel, log_channel,
                 embed_color=discord.Colour.from_rgb(226, 226, 226),
                 embed_author="Seoultech"):
        """공통 초기화: 설정 경로, 채널, 기본 URL 등"""
        self.category_key = category_key         # 예: "seoultechContest"
        self.base_url = base_url                 # 사이트별 기본 URL
        self.settings_path = settings_path
        self.settings_toml = settings_toml
        self.main_channel = main_channel
        self.log_channel = log_channel
        self.embed_color = embed_color           # 디폴트 임베드 색상
        self.embed_author = embed_author         # 임베드 저자표시 문자열
    async def check(self):
        current_time = datetime.now(timezone(timedelta(hours=9)))
        current_newest = self.settings_toml["CLIENT"]["NEWEST_POST"][self.category_key]
        new_post, posts = self.get_latest_posts()

        # 1) 응답 실패
        if new_post is None:
            await self.log_channel.send(f"[{current_time}]|Failed_to_fetch_posts|[{self.category_key}]")
            return False

        # 2) ID가 같으면 (실제 최신글 없음)
        if new_post.id == current_newest["ID"]:
            await self.log_channel.send(f"[{current_time}]|There_is_nothing_new|[{self.category_key}]")
            return True

        # 3) else: new_post.id != current -> 새 글이 있을 수도
        posts.sort(key=lambda post: (post.date, self._id_to_int(post.id)))
        sent = False
        for post in posts:
            if self._is_post_newer(post, current_newest):
                # Embed 전송 로직...
                # 1) Embed 전송
                embed = discord.Embed(
                    title=f"[{post.id}] {post.title}",
                    description=f"Link: {post.link}",
                    color=self.embed_color
                )
                embed.set_author(name=self.embed_author)
                embed.set_footer(text=f"New Notification by {self.category_key}")
                message = await self.main_channel.send(embed=embed)

                # 2) 리액션 추가
                save_emoji = self.settings_toml["DISCORD"]["EMOJIS"]["SAVE"][0]
                await message.add_reaction(save_emoji)

                # 3) 로그 채널에 업데이트 로그
                await self.log_channel.send(
                    f"[{current_time}]|The_latest_notification_has_been_updated|"
                    f"['{current_newest['ID']}'->'{post.id}']|[{self.category_key}]"
                )
                append_notice_history(
                    settings_path=self.settings_path,
                    category_key=self.category_key,
                    post=post,
                    recorded_at=current_time,
                )
                sent = True
                # 저장 및 최신화
                self.update_newest_post(post)
        # 4) 한 건도 보내지 않았다면, 아무 것도 없다는 로그
        if not sent:
            await self.log_channel.send(f"[{current_time}]|There_is_nothing_new|[{self.category_key}]")
        return True

    def _id_to_int(self, post_id: str) -> int:
        """게시물 ID의 숫자 부분을 정수로 변환 (숫자가 아닌 경우 0)."""
        numeric = post_id[1:]  # 첫 글자 ('N' 또는 'P') 제외
        return int(numeric) if numeric.isdigit() else 0

    def _is_post_newer(self, post, current_newest: dict) -> bool:
        """주어진 게시물이 current_newest 이후에 올라온 것인지 확인."""
        post_date = datetime.strptime(post.date, "%Y-%m-%d")
        curr_date = datetime.strptime(current_newest["DATE"], "%Y-%m-%d")
        if post_date > curr_date:
            return True
        if post_date == curr_date:
            # 날짜가 같다면 ID 숫자 비교
            return self._id_to_int(post.id) > self._id_to_int(current_newest["ID"])
        return False

    def update_newest_post(self, post):
        """settings.toml 파일의 최신 게시물 기록을 갱신."""
        self.settings_toml["CLIENT"]["NEWEST_POST"][self.category_key] = {
            "ID": post.id, "DATE": post.date, "URL": post.link
        }
        with open(self.settings_path, 'w', encoding='utf-8') as f:
            toml.dump(self.settings_toml, f)

    def get_latest_posts(self):
        """최신 게시물 및 전체 게시물 리스트를 반환 – 서브클래스에서 구현."""
        raise NotImplementedError("Subclasses must implement get_latest_posts() for each site.")



def log_exceptions(func):
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            logger = logging.getLogger(__name__)
            now = datetime.now(timezone(timedelta(hours=9)))
            # 파일/콘솔 로깅
            logger.exception(f"[{self.category_key}] 에러 발생: {e}")
            # Discord 로그 채널에도 요약 전송
            await self.log_channel.send(
                f"[{now}]|Task_{self.category_key}_failed|{e}"
            )

            tb = traceback.format_exc()
            current_time = datetime.now(timezone(timedelta(hours=9)))
            await self.log_channel.send(f"[{current_time}]|{type(self).__name__}_exception|{e}\n```{tb}```")
            return False
    return wrapper
