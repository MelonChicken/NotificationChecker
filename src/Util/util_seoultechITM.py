import requests
from bs4 import BeautifulSoup
import discord

from Util.notification_checker_base import NotificationCheckerBase


class PostITM:
    def __init__(self, post_id = "UNK", post_title="title",post_date = "YYYY-MM-DD", post_link = "link"):
        self.id = post_id
        self.title = post_title
        self.link = post_link
        self.date = post_date
        self.content = "unknown"

    def add_content(self):
        response = requests.get(self.link)
        if response.status_code != 200:
            self.content = f"ResponseError[status_code: {response.status_code}]"
        soup = BeautifulSoup(response.content, 'html.parser')
        content_box = soup.find("table", "tbl_list").find("tbody").find("td", "cont").get_text().strip()
        self.content = content_box


class SeoultechITMChecker(NotificationCheckerBase):

    def __init__(self, settings_path, settings_toml, main_channel, log_channel):
        super().__init__(category_key="seoultechITM",
                         base_url="https://itm.seoultech.ac.kr/bachelor_of_information/notice/",
                         settings_path=settings_path,
                         settings_toml=settings_toml,
                         main_channel=main_channel,
                         log_channel=log_channel,
                         embed_color=discord.Colour.from_rgb(141, 154, 141),
                         embed_author="Seoultech ITM")
        # 필요시 다른 초기화 작업 추가
    def get_latest_posts(self):
        url = self.base_url
        response = requests.get(url)
        if response.status_code != 200:
            return None, []

        soup = BeautifulSoup(response.content, 'html.parser')
        post_rows = soup.find("tbody").find_all("tr", class_="body_tr")
        posts = []

        for row in post_rows:
            try:
                raw_id_box = row.find("td", "dn1")
                title = row.find("td", "body_col_title dn2").find("a").get_text(strip=True)
                date = row.find("td", "body_col_regdate dn5").get_text(strip=True)
                link = self.base_url + row.find("td", "body_col_title dn2").find("a")["href"]

                if ("notice" or "공지") in str(raw_id_box.get_text):
                    # 공지글은 날짜 기반 ID 부여
                    numeric_part = date.replace("-", "")[-4:]
                    post_id = f"N{numeric_part}"
                else:
                    post_id = f"P{raw_id_box.get_text(strip=True)}"

                posts.append(PostITM(post_id, title, date, link))

            except Exception as e:
                continue  # 파싱 실패 시 해당 게시물 무시

        posts.sort(key=lambda x: (x.date, x.id), reverse=True)
        newest = posts[0] if posts else None
        return newest, posts

# get_newest_content 함수 (명령어 수동 호출용)
async def get_newest_content_seoultechITM(id: str, url: str, target_channel, log_channel, current_time, save_emoji):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(f"Failed to load content: {response.status_code}")

        soup = BeautifulSoup(response.content, 'html.parser')
        container = soup.find("table", "tbl_list").find("tbody")
        rows = container.find_all("tr")

        title_row = rows[0].find_all("td")
        author_row = rows[1].find("td")
        content_row = container.find("td", "cont")

        title = title_row[0].get_text(strip=True)
        date = title_row[1].get_text(strip=True)
        author = author_row.get_text(strip=True)
        content = content_row.get_text(strip=True)

        # 내용 요약
        title = title[:20] + "..." if len(title) > 20 else title
        content = content[:99] + "\n\n...(see more)" if len(content) > 100 else content

        embed = discord.Embed(title=f"[{id}]\n{title}", description=content, url=url,
                              color=discord.Colour.from_rgb(226, 226, 226))
        embed.set_author(name=f"{author} [{date}]")
        embed.set_footer(text="Newest Post in the Seoultech ITM")

        message = await target_channel.send(embed=embed)
        await message.add_reaction(save_emoji)
        await log_channel.send(
            f"[{current_time}]|The_latest_notification_in_the_Seoultech_ITM_has_been_called|[{id}]")

    except Exception as e:
        await log_channel.send(f"[{current_time}]|Error_loading_ITM_post_content|{e}")