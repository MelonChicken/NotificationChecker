import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import discord
import toml



class PostContest:
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


class NotificationCheckerSeoultechContest:

    def __init__(self, settings_path, settings_toml,
                 main_channel, log_channel,
                 url="https://www.seoultech.ac.kr/service/board/rec/"):

        self.settings_path = settings_path
        self.settings_toml = settings_toml
        self.main_channel = main_channel
        self.log_channel = log_channel
        self.url = url

    async def check(self):

        settings_path = self.settings_path
        settings_toml = self.settings_toml
        main_channel =self.main_channel
        log_channel = self.log_channel
        current_time = datetime.now(timezone(timedelta(hours=9)))

        try:
            current_newest_post = settings_toml["CLIENT"]["NEWEST_POST"]["seoultechContest"]
            new_post, posts = get_response_seoultechContest(base_url=self.url)


            # If there is no new notification on the ITM website
            if new_post.id == current_newest_post["ID"]:
                await log_channel.send(f"[{current_time}]|There_is_nothing_new_on_the_website|[{type(self).__name__[19:]}]")

            else:
                posts = sorted(posts, key=lambda x : (x.date, x.id), reverse=False)

                for post in posts:
                    if datetime.strptime(current_newest_post["DATE"], "%Y-%m-%d") <= datetime.strptime(post.date, "%Y-%m-%d") and not current_newest_post["ID"] == post.id:
                        # If the newest post which was just published is newer than the prior new post
                        embed = discord.Embed(title=f"[{post.id}] {post.title}...",
                                              description=f"Link: {post.link}",
                                              color=discord.Colour.from_rgb(141, 154, 141))

                        embed.set_author(name='Seoultech Contest')
                        embed.set_footer(text=f"New Notification by {type(self).__name__[19:]}")
                        message = await main_channel.send(embed=embed)
                        check_emoji = settings_toml["DISCORD"]["EMOJIS"]["SAVE"][0]
                        await message.add_reaction(check_emoji)
                        await log_channel.send(f"[{current_time}]|The_latest_notification_has_been_updated|['{current_newest_post["ID"]}'->'{post.id}']|[{type(self).__name__[19:]}]")

                        self.update_newest_post(post, settings_path=settings_path, settings_toml=settings_toml)
                        current_newest_post = {"ID": post.id, "DATE": post.date, "URL":post.link}
            return True

        except Exception as e:
            sys.stdout.write(f"Task {type(self).__name__} failed with error: {e}")
            await log_channel.send(f"[{current_time}]|Task_{type(self).__name__}_failed_with_error:{e}|[{type(self).__name__[19:]}]")
            return False

    def update_newest_post(self, post: PostContest, settings_path, settings_toml):

        settings_toml["CLIENT"]["NEWEST_POST"]["seoultechContest"]["ID"] = post.id
        settings_toml["CLIENT"]["NEWEST_POST"]["seoultechContest"]["DATE"] = post.date
        settings_toml["CLIENT"]["NEWEST_POST"]["seoultechContest"]["URL"] = post.link

        with open(settings_path, 'w', encoding="utf-8") as f:
            toml.dump(settings_toml, f)

def get_response_seoultechContest(base_url = "https://www.seoultech.ac.kr/service/board/rec/"):
    url = f"{base_url}"
    response = requests.get(url)
    if response.status_code != 200:
        return None  # Handle error
    else:
        posts = get_intial_info_seoultechContest(response=response, base_url=base_url)
        posts_sorted_by_date = sorted(posts, key= lambda x: (x.date, x.id), reverse=True)
        return posts_sorted_by_date[0], posts_sorted_by_date

def get_intial_info_seoultechContest(response, base_url):

    soup = BeautifulSoup(response.content, 'html.parser')
    posts = soup.find("tbody").find_all("tr", class_ = "body_tr")
    posts_info = []
    # Extract title and link of the latest notice
    for post in posts:
        post_id = post.find('td', "dn1")
        post_title_box = post.find('td', "dn2")
        title = post_title_box.find("a").text.strip()
        date = post.find('td', "dn5").text.strip()
        link = base_url + post_title_box.find("a").attrs['href']

        if ("notice" or "공지") in str(post_id.get_text):
            formatted_date = str(date).replace('-', '', 2)[-4:]
            post_id = f"N{formatted_date}"
        else:
            post_id = f"P{post_id.text.strip()}"

        post_class = PostContest(post_id=post_id, post_title=title, post_link=link, post_date=date)
        posts_info.append(post_class)
    return posts_info

async def get_newest_content_SeoultechContest(id: str, url: str,
                                              target_channel, log_channel, current_time,
                                              save_emoji):
    response = requests.get(url)

    if response.status_code != 200:
        content = f"ResponseError[status_code: {response.status_code}]"
        return content
    else:
        soup = BeautifulSoup(response.content, 'html.parser')

        notification_container = soup.find("table", "tbl_view").find("tbody")
        notification_container_list = notification_container.find_all("tr")
        notification_title = notification_container_list[0].find("td").get_text().strip()
        notification_author_date = notification_container_list[1].find_all("td")
        notification_author = notification_author_date[0].get_text().strip()
        notification_date = notification_author_date[-1].get_text().strip()
        notification_content = notification_container.find("td", "cont").get_text().strip()

        if 20 < len(notification_title):
            notification_title = notification_title[:20] + "..."

        if 100 < len(notification_content):
            notification_content = notification_content[:99] + "\n\n...(see more)"


        embed = discord.Embed(title=f"[{id}]\n{notification_title}",
                              description=notification_content,
                              url=url,
                              color=discord.Colour.from_rgb(226, 226, 226),)

        embed.set_author(name=f"{notification_author} [{notification_date}]")
        embed.set_footer(text=f"Newest Post in the Seoultech Contest")

        message = await target_channel.send(embed=embed)
        check_emoji = save_emoji
        await message.add_reaction(check_emoji)
        await log_channel.send(f"[{current_time}]|The_latest_notification_in_the_Seoultech_Contest_has_been_called|[{id}]")
