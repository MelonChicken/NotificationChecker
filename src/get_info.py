import requests
from bs4 import BeautifulSoup

class Post:
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


def get_response_seoultechITM(base_url = "https://itm.seoultech.ac.kr/bachelor_of_information/notice/", page_num = 1):
    url = f"{base_url}?page={page_num}"
    response = requests.get(url)
    if response.status_code != 200:
        return None  # Handle error
    else:
        posts = get_intial_info_seoultechITM(response=response, base_url=base_url)
        posts_sorted_by_date = sorted(posts, key= lambda x: x.date, reverse=True)
        return posts_sorted_by_date[0], posts_sorted_by_date

    
        
def get_intial_info_seoultechITM(response, base_url):

    soup = BeautifulSoup(response.content, 'html.parser')
    posts = soup.find("tbody").find_all("tr", class_ = "body_tr")
    posts_info = []
    # Extract title and link of the latest notice
    for post in posts:
        post_id = post.find('td', "dn1")
        post_title_box = post.find('td', "body_col_title dn2")
        title = post_title_box.find("a").text.strip()
        date = post.find('td', "body_col_regdate dn5").text.strip()
        link = base_url + post_title_box.find("a").attrs['href']

        if "notice" in str(post_id.get_text):
            formatted_date = str(date).replace('-', '', 2)[-4:]
            post_id = f"N{formatted_date}"
        else:
            post_id = f"P{post_id.text.strip()}"

        post_class = Post(post_id=post_id, post_title=title, post_link=link, post_date=date)
        #  post_class.add_content()
        #  print(post_class.id, post_class.title, post_class.date, post_class.link[:10], post_class.content, sep="    ")
        posts_info.append(post_class)
    return posts_info

newest_post, whole_post = get_response_seoultechITM()
#  print(newest_post.id, newest_post.title, newest_post.date, newest_post.link[:10], newest_post.content, sep="    ")