import os
import requests
from datetime import datetime as dt
from bs4 import BeautifulSoup
from colorama import init
from threading import Thread
import time

SPACE_ALIGNMENT = 100
TIME_FOR_BREAKING_NEWS = 60  # 1 min

class News:
    def __init__(self):
        self.breaking = "No"
        self.headline = ""
        self.time_stamp = ""
        self.source_url = ""
        self.story = ""

    def serialize(self):
        return {
            "breaking_news": self.breaking,
            "headline": self.headline.replace("'", "<ap>"),
            "time": self.time_stamp,
            "source": self.source_url,
            "story": self.story.replace("'", "<ap>")
        }

class NewsTicker:
    def __init__(self):
        self.news = []
        self.breaking_news_update = []
        self.connected = False
        
    def news_mapper(self, news_data: News):
        news = News()

        try:
            news.breaking = news_data["breaking_news"]
        except:
            news.breaking = "No"

        try:
            news.headline = news_data["headline"]
        except:
            pass

        try:    
            news.time_stamp = news_data["time"]
        except:
            news.time_stamp = dt.now().strftime('%I:%M %p')
        
        try:
            news.source_url = news_data["source"]
        except:
            pass

        try:
            news.story = news_data["story"]
        except:
            pass

        return news.serialize()

    def count(self):
        return len(self.news)

    def breaking_news_daemon(self):
        while True:
            # connect to CNN website
            cnn_soup, cnn_url = self.connect()
            breaking_news_thread = Thread(target=self.scrape_breaking_news, args=(cnn_soup, cnn_url,))
            breaking_news_thread.setDaemon(True)
            breaking_news_thread.start()
            time.sleep(TIME_FOR_BREAKING_NEWS)

    def breaking_news_watch(self):
        return len(self.breaking_news_update) > 0

    def scrape_breaking_news(self, cnn_soup, base_url):
        temp = []
        try:
            cnn_breaking_news = cnn_soup.find_all("div", { "class": "breaking-news-content runtext-container"})
            
            for news in cnn_breaking_news:
                headline = news.find("a").text.strip()
                news_data = {"breaking_news": True, "headline": headline, "source": base_url}

                mapped_news_data = self.news_mapper(news_data)
                temp.append(mapped_news_data)

            if len(self.breaking_news_update) <= 0:
                self.news.extend(temp)
                self.breaking_news_update.extend(temp)

        except:
            print("Scraping failed. Can't get breaking news..")

    def scrape_latest_news(self, cnn_soup, base_url):
        try:
            cnn_latest = cnn_soup.find_all("article", {"class": "media"})

            for elem in cnn_latest:
                headline = elem.find("h4").find("a").text.strip()
                link = base_url + elem.find("h4").find("a")["href"]
                
                paragraphs = elem.find_all("p")
                time_stamp = paragraphs[0].text.strip()
                story = paragraphs[1].text.strip()

                news_data = {"headline": headline, "source": link, "time": time_stamp, "story": story}
                self.news.append(self.news_mapper(news_data))

                # print(f"{headline} ({time_stamp}) \n {link}", end="\n\n")

            # https://www.manilatimes.net/news/latest-stories/breakingnews/

        except:
            print("Scraping failed. Can't get latest news..")

    def get_news(self):
        if len(self.news) < 1:
            # return immediately if no list of headlines to show
            print("\n **No new headlines found.")
            return list()
        
        return self.news

    def connect(self):
        cnn_soup = None
        cnn_url = ""

        try:
            cnn_response = requests.get("https://cnnphilippines.com/latest")
            cnn_url = os.path.dirname(cnn_response.url)
            cnn_soup = BeautifulSoup(cnn_response.text, "html.parser")
            self.connected = True

        except:
            print("Cannot connect to source url.")
            self.connected = False
        
        return cnn_soup, cnn_url

    def fetch_news(self):
        self.news = []
        cnn_soup = None
        cnn_url = ""

        print("\n Fetching news from internet...")
        cnn_soup, cnn_url = self.connect()

        # scrape news from various websites
        self.scrape_breaking_news(cnn_soup, cnn_url)
        self.scrape_latest_news(cnn_soup, cnn_url)
        self.save_as_json()

    def save_as_json(self):
        # create the json file type
        with open("NewsTicker.json", "w", encoding="utf-8") as fw:
            news = {
                "news": self.news
            }
            fw.write(str(news).replace("'", "\"").replace("<ap>", "'"))

    def create_news_banner(self, news):
        title_color = "\033[2;30;47m"
        source_color = "\033[1;36;49m"
        color_reset = "\033[0;39;49m"

        headline = "{} {} ".format(title_color, news["headline"].replace("<ap>", "'"))
        story = "{} {} ".format(color_reset, news["story"])
        source = "{} {}".format(source_color, news["source"].replace("<ap>", "'"))

        print(headline)
        print("{}more on{}".format(story, source), "\n")

    def show_news(self, isBanner=True):
        news_idx = 0
        current_news = []
        
        if len(self.news) < 1:
            # return immediately if no list of headlines to show
            print("\n **No new headlines found.")
            return

        # daemon thread to check breaking news from time to time
        breaking_news_thread = Thread(target=self.breaking_news_daemon)
        breaking_news_thread.setDaemon(True)
        breaking_news_thread.start()

        def _create_news_ticker():
            news_list = self.news
            
            isBreakingNews = False
            window_height = 90

            if self.breaking_news_watch():
                window_height = "110 /top"
                news_list = self.breaking_news_update
                isBreakingNews = True

            os.system(f"CMDOW @ /ren \"News Watcher\" /mov 11 -35 /siz 1550 {window_height}")

            breaking_red_color = "\033[1;37;41m"
            connection_red_color = "\033[1;31;49m"
            color_reset = "\033[2;39;49m"

            headline = current_news["headline"].replace("<ap>", "'")
            time_stamp = current_news["time"]
            ticker_detail = f"{headline} | {time_stamp} ({news_idx} of {len(news_list)})".center(168)
            deets_length = len(ticker_detail)

            counter = 0
            while True:
                os.system("cls")
                
                counter += 2
                # slice some parts of headline to make a scrolling effect
                animate_ticker_details = ticker_detail[counter:(deets_length + counter)] + ticker_detail[0:counter]
                
                print("\n\n")
                if not self.connected:
                    print(f"{connection_red_color} * No Internet Connection * {color_reset}".center(180))
                elif isBreakingNews:
                    print(f"{breaking_red_color} * BREAKING NEWS * {color_reset}".center(180))

                # headline is almost full row..
                if len(ticker_detail) > 168:
                    
                    if "." in ticker_detail:
                        # let's break it into separate sentences.
                        for sentence in ticker_detail.split("."):
                            sentence = f"{sentence}.".center(168)
                            size = len(sentence)
                            print(f"{sentence[counter:(size + counter)] + sentence[0:counter]}")
                
                else:
                    # show the headline news
                    print(f"{animate_ticker_details}")

                # pause for sometime before scrolling forward the headline
                if counter == 2:
                    time.sleep(3)

                # pause for sometime before moving to next headline
                if counter >= deets_length:
                    time.sleep(3)
                    break

        
        # initialize text coloring
        init(autoreset=True)
        print("\n")

        while True:
            if self.breaking_news_watch():
                # priority ticker for BREAKING NEWS
                for idx, breakingnews in enumerate(self.breaking_news_update):
                    news_idx = idx + 1
                    current_news = breakingnews
                    
                    if isBanner:
                        self.create_news_banner(breakingnews)
                    else:
                        _create_news_ticker()

                # empty the list so that we would know if there will be new list of Breaking News
                self.breaking_news_update = []

            else:
                # ticker for latest news headlines
                for idx, news in enumerate(self.news):
                    news_idx = idx + 1
                    current_news = news

                    # halt news watch ticker and display the breaking news
                    if self.breaking_news_watch():
                        break

                    if isBanner:
                        self.create_news_banner(news)
                    else:
                        _create_news_ticker()
            
            self.fetch_news()
            self.show_news(isBanner)


if __name__ == "__main__":
    news = NewsTicker()

    while True:
        os.system("cls")
        try:
            news.fetch_news()
            news.show_news(False)

        except KeyboardInterrupt:
            break
        except Exception as ex:
            print(str(ex))
            print(" Trying to re-connect...")

        time.sleep(5)