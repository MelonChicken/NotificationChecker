from urllib.parse import urljoin

import discord
import requests
from bs4 import BeautifulSoup

from Util.notification_checker_base import NotificationCheckerBase
from Util.notice_identity import Notice, is_major_notice_text, make_stable_id


class SeoultechITMChecker(NotificationCheckerBase):
    def __init__(self, settings_path, settings_toml, main_channel, log_channel):
        super().__init__(
            category_key="seoultechITM",
            base_url="https://itm.seoultech.ac.kr/bachelor_of_information/notice/",
            settings_path=settings_path,
            settings_toml=settings_toml,
            main_channel=main_channel,
            log_channel=log_channel,
            embed_color=discord.Colour.from_rgb(141, 154, 141),
            embed_author="Seoultech ITM",
        )

    def get_posts_page(self, page: int):
        response = requests.get(self.build_page_url(page))
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.content, "html.parser")
        tbody = soup.find("tbody")
        if tbody is None:
            return []

        posts = []
        for row in tbody.find_all("tr", class_="body_tr"):
            try:
                raw_id_box = row.find("td", "dn1")
                title_link = row.find("td", "body_col_title dn2").find("a")
                raw_id = raw_id_box.get_text(strip=True)
                title = title_link.get_text(strip=True)
                date = row.find("td", "body_col_regdate dn5").get_text(strip=True)
                link = urljoin(self.base_url, title_link["href"])
                is_major = is_major_notice_text(raw_id)
                legacy_id = f"N{date.replace('-', '')[-4:]}" if is_major else f"P{raw_id}"

                posts.append(
                    Notice(
                        source="seoultech",
                        category=self.category_key,
                        stable_id=make_stable_id(link, self.category_key, date, title),
                        title=title,
                        date=date,
                        url=link,
                        is_major_notice=is_major,
                        legacy_id=legacy_id,
                    )
                )
            except Exception:
                continue

        posts.sort(key=lambda post: (post.date, post.stable_id), reverse=True)
        return posts

    def get_latest_posts(self):
        posts = self.get_posts_page(1)
        if posts is None:
            return None, []
        newest = posts[0] if posts else None
        return newest, posts


async def get_newest_content_seoultechITM(id: str, url: str, target_channel, log_channel, current_time, save_emoji):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(f"Failed to load content: {response.status_code}")

        soup = BeautifulSoup(response.content, "html.parser")
        container = soup.find("table", "tbl_list").find("tbody")
        rows = container.find_all("tr")

        title_row = rows[0].find_all("td")
        author_row = rows[1].find("td")
        content_row = container.find("td", "cont")

        title = title_row[0].get_text(strip=True)
        date = title_row[1].get_text(strip=True)
        author = author_row.get_text(strip=True)
        content = content_row.get_text(strip=True)

        title = title[:20] + "..." if len(title) > 20 else title
        content = content[:99] + "\n\n...(see more)" if len(content) > 100 else content

        embed = discord.Embed(
            title=f"[{id}]\n{title}",
            description=content,
            url=url,
            color=discord.Colour.from_rgb(226, 226, 226),
        )
        embed.set_author(name=f"{author} [{date}]")
        embed.set_footer(text="Newest Post in the Seoultech ITM")

        message = await target_channel.send(embed=embed)
        await message.add_reaction(save_emoji)
        await log_channel.send(
            f"[{current_time}]|The_latest_notification_in_the_Seoultech_ITM_has_been_called|[{id}]"
        )

    except Exception as e:
        await log_channel.send(f"[{current_time}]|Error_loading_ITM_post_content|{e}")
