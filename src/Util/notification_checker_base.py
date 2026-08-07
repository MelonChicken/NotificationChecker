import logging
import traceback
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import discord

from api.notice_summary import append_notice_history, load_seen_notice_keys
from Util.notice_identity import format_notice_display_tag, notice_history_key


class NotificationCheckerBase:
    MAX_SCAN_PAGES = 5

    def __init__(
        self,
        *,
        category_key: str,
        base_url: str,
        settings_path: str,
        settings_toml: dict,
        main_channel,
        log_channel,
        embed_color=discord.Colour.from_rgb(226, 226, 226),
        embed_author="Seoultech",
    ):
        self.category_key = category_key
        self.base_url = base_url
        self.settings_path = settings_path
        self.settings_toml = settings_toml
        self.main_channel = main_channel
        self.log_channel = log_channel
        self.embed_color = embed_color
        self.embed_author = embed_author

    async def check(self):
        current_time = datetime.now(timezone(timedelta(hours=9)))
        scan_result = self.collect_new_posts(load_seen_notice_keys(self.settings_path))

        if not scan_result["success"]:
            await self.log_channel.send(f"[{current_time}]|Failed_to_fetch_posts|[{self.category_key}]")
            return False

        new_posts = scan_result["new_posts"]
        if not new_posts:
            await self.log_channel.send(f"[{current_time}]|There_is_nothing_new|[{self.category_key}]")
            return True

        sent = False
        for post in new_posts:
            if await self.send_post(post):
                append_notice_history(
                    settings_path=self.settings_path,
                    category_key=self.category_key,
                    post=post,
                    recorded_at=current_time,
                )
                sent = True
                await self.log_channel.send(
                    f"[{current_time}]|Notification_sent|[{post.stable_id}]|[{self.category_key}]"
                )

        if not sent:
            await self.log_channel.send(
                f"[{current_time}]|New_notifications_found_but_send_failed|[{self.category_key}]"
            )
        return True

    def collect_new_posts(self, seen_keys: set[tuple[str, str, str]]):
        new_posts = []
        stop_scan = False

        for page in range(1, self.MAX_SCAN_PAGES + 1):
            posts = self.get_posts_page(page)
            if posts is None:
                return {"success": False, "new_posts": []}
            if not posts:
                break

            for post in posts:
                key = notice_history_key(post.source, post.category, post.stable_id)

                if post.is_major_notice:
                    if key not in seen_keys:
                        new_posts.append(post)
                    continue

                if key in seen_keys:
                    stop_scan = True
                    break

                new_posts.append(post)

            if stop_scan:
                break

        new_posts.sort(key=lambda post: (post.date, post.stable_id))
        return {"success": True, "new_posts": new_posts}

    async def send_post(self, post) -> bool:
        try:
            display_tag = format_notice_display_tag(post)
            embed = discord.Embed(
                title=f"[{display_tag}] {post.title}",
                description=f"Link: {post.link}",
                color=self.embed_color,
            )
            embed.set_author(name=self.embed_author)
            embed.set_footer(text=f"New Notification by {self.category_key}")
            message = await self.main_channel.send(embed=embed)

            save_emoji = self.settings_toml["DISCORD"]["EMOJIS"]["SAVE"][0]
            await message.add_reaction(save_emoji)
            return True
        except Exception as e:
            current_time = datetime.now(timezone(timedelta(hours=9)))
            await self.log_channel.send(
                f"[{current_time}]|Failed_to_send_notification|[{self.category_key}]|"
                f"[{getattr(post, 'stable_id', '')}]|{e}"
            )
            return False

    def get_posts_page(self, page: int):
        if page == 1:
            new_post, posts = self.get_latest_posts()
            if new_post is None:
                return None
            return posts
        return []

    def build_page_url(self, page: int) -> str:
        parsed = urlsplit(self.base_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["nowpage"] = str(page)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))

    def get_latest_posts(self):
        raise NotImplementedError("Subclasses must implement get_latest_posts() for each site.")


def log_exceptions(func):
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            logger = logging.getLogger(__name__)
            now = datetime.now(timezone(timedelta(hours=9)))
            logger.exception(f"[{self.category_key}] error: {e}")
            await self.log_channel.send(f"[{now}]|Task_{self.category_key}_failed|{e}")

            tb = traceback.format_exc()
            current_time = datetime.now(timezone(timedelta(hours=9)))
            await self.log_channel.send(
                f"[{current_time}]|{type(self).__name__}_exception|{e}\n```{tb}```"
            )
            return False

    return wrapper
