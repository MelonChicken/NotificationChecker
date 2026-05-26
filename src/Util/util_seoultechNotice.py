import requests
from bs4 import BeautifulSoup
import discord

from Util.notification_checker_base import NotificationCheckerBase


class PostNotice:
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
        content_box = soup.find("table", "tbl_list").find("tbody").find_all("td", "body_tr").get_text().strip()
        self.content = content_box

class SeoultechNoticeChecker(NotificationCheckerBase):

    def __init__(self, settings_path, settings_toml, main_channel, log_channel):
        super().__init__(category_key="seoultechNotice",
                         base_url="https://www.seoultech.ac.kr/service/info/notice",
                         settings_path=settings_path,
                         settings_toml=settings_toml,
                         main_channel=main_channel,
                         log_channel=log_channel,
                         embed_color=discord.Colour.from_rgb(141, 154, 141),
                         embed_author="Seoultech Notice")
        # 필요시 다른 초기화 작업 추가

    def get_latest_posts(self):
        # 1. 웹페이지 요청 및 응답 확인
        response = requests.get(self.base_url)
        if response.status_code != 200:
            return None, []  # 응답 실패 시 (None, []) 반환하여 상위에서 처리
        soup = BeautifulSoup(response.content, 'html.parser')
        posts = []
        # 2. HTML 파싱하여 게시물 목록 구성
        for row in soup.find("tbody").find_all("tr", class_="body_tr")[1:]:
            post_id_box = row.find('td', "dn1")
            title = row.find('td', "dn2").find("a").get_text(strip=True)
            date = row.find('td', "dn5").get_text(strip=True)
            link = self.base_url + row.find('td', "dn2").find("a")['href']
            # 공지글 식별 및 ID 생성 로직
            if ("notice" or "공지") in str(post_id_box.get_text):
                # 날짜에서 연월일 숫자만 추출 (예: '2023-06-01' -> '0601')
                formatted = date.replace('-', '')[-4:]
                post_id = f"N{formatted}"
            else:
                post_id = f"P{post_id_box.get_text(strip=True)}"
            posts.append(PostNotice(post_id, title, date, link))
        # 3. 최신순으로 정렬하여 (new_post, posts) 튜플 반환
        posts.sort(key=lambda post: (post.date, post.id), reverse=True)
        newest_post = posts[0] if posts else None
        return newest_post, posts

async def get_newest_content_seoultechNotice(
    id: str,
    url: str,
    target_channel,
    log_channel,
    current_time,
    save_emoji: str
):
    try:
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        view_table = soup.find("table", class_="tbl_view")
        tbody      = view_table.find("tbody")
        rows       = tbody.find_all("tr")  # class 필터 제거

        # 제목
        title = rows[0].find("td").get_text(strip=True)

        # 작성자 / 날짜
        tds    = rows[1].find_all("td")
        author = tds[0].get_text(strip=True)
        date   = tds[-1].get_text(strip=True)

        # 본문
        content_td = tbody.find("td", class_="cont")
        content    = content_td.get_text("\n", strip=True)

        # 요약 처리
        if len(title) > 50:
            title = title[:50] + "..."
        if len(content) > 200:
            summary = content[:199] + "\n\n...(see more)"
        else:
            summary = content

        # 임베드 생성
        embed = discord.Embed(
            title=f"[{id}] {title}",
            description=summary,
            url=url,
            color=discord.Colour.from_rgb(30, 144, 255)
        )
        embed.set_author(name=f"{author} [{date}]")
        embed.set_footer(text="Newest Post in the Seoultech Notice")

        msg = await target_channel.send(embed=embed)
        await msg.add_reaction(save_emoji)
        await log_channel.send(
            f"[{current_time}]|The_latest_notification_in_the_Seoultech_Notice_has_been_called|[{id}]"
        )

    except requests.RequestException as e:
        await log_channel.send(f"[{current_time}]|Failed_to_request_seoultechNotice_page|{e}")
    except Exception as e:
        await log_channel.send(f"[{current_time}]|Error_in_get_newest_content_seoultechNotice|{e}")
