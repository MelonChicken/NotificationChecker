import requests
from bs4 import BeautifulSoup
import discord

from Util.notification_checker_base import NotificationCheckerBase


class PostJob:
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
        content_box = soup.find("table", "tbl_view").find("tbody").find("td", "cont").get_text().strip()
        self.content = content_box

class SeoultechJobChecker(NotificationCheckerBase):
    """
    NotificationCheckerBase를 상속하여
    서울과기대 Job 공지 전용으로 크롤링·알림 기능을 제공하는 클래스
    """
    def __init__(self, settings_path, settings_toml, main_channel, log_channel):
        super().__init__(
            category_key="seoultechJob",
            base_url="https://www.seoultech.ac.kr/service/info/job/",
            settings_path=settings_path,
            settings_toml=settings_toml,
            main_channel=main_channel,
            log_channel=log_channel,
            embed_color=discord.Colour.from_rgb(179, 182, 183),
            embed_author="Seoultech Job"
        )

    def get_latest_posts(self):
        """
        Job 공지 목록을 파싱하여 가장 최신 Post 객체와 전체 리스트를 반환
        """
        response = requests.get(self.base_url)
        if response.status_code != 200:
            return None, []

        soup = BeautifulSoup(response.content, 'html.parser')
        rows = soup.find("tbody").find_all("tr", class_="body_tr")
        posts = []

        for row in rows:
            try:
                raw_id_box = row.find('td', "dn1")
                title = row.find('td', "dn2").find("a").get_text(strip=True)
                date = row.find('td', "dn5").get_text(strip=True)
                href = row.find('td', "dn2").find("a")["href"]
                link = self.base_url + href

                # 공지글 식별 및 ID 생성
                if ("notice" or "공지") in str(raw_id_box.get_text):
                    numeric = date.replace('-', '')[-4:]
                    post_id = f"N{numeric}"
                else:
                    post_id = f"P{raw_id_box.get_text(strip=True)}"

                posts.append(PostJob(post_id, title, date, link))

            except Exception:
                # 개별 행 파싱 실패 시 건너뜀
                continue

        # (날짜, ID) 기준 내림차순 정렬
        posts.sort(key=lambda post: (post.date, post.id), reverse=True)
        newest = posts[0] if posts else None
        return newest, posts


async def get_newest_content_seoultechJob(
    id: str,
    url: str,
    target_channel,
    log_channel,
    current_time,
    save_emoji: str
):
    """
    수동 호출용: 가장 최신의 Job 공지 내용을 임베드로 Discord에 전송
    """
    try:
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        container = soup.find("table", "tbl_view").find("tbody")
        rows = container.find_all("tr")

        # 제목 / 작성자 / 작성일
        title = rows[0].find("td").get_text(strip=True)
        author_date = rows[1].find_all("td")
        author = author_date[0].get_text(strip=True)
        date = author_date[-1].get_text(strip=True)

        # 본문
        content = container.find("td", "cont").get_text(strip=True)

        # 길이 제한
        if len(title) > 20:
            title = title[:20] + "..."
        if len(content) > 100:
            content = content[:99] + "\n\n...(see more)"

        # 임베드 메시지 생성
        embed = discord.Embed(
            title=f"[{id}] {title}",
            description=content,
            url=url,
            color=discord.Colour.from_rgb(226, 226, 226)
        )
        embed.set_author(name=f"{author} [{date}]")
        embed.set_footer(text="Newest Post in the Seoultech Job")

        # 전송 및 반응 추가
        message = await target_channel.send(embed=embed)
        await message.add_reaction(save_emoji)

        # 호출 로그
        await log_channel.send(
            f"[{current_time}]|The_latest_notification_in_the_Seoultech_Job_has_been_called|[{id}]"
        )

    except requests.RequestException as e:
        await log_channel.send(f"[{current_time}]|Failed_to_request_job_page|{e}")
    except Exception as e:
        await log_channel.send(f"[{current_time}]|Error_in_get_newest_post_seoultechJob|{e}")
