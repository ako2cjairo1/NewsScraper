import os
import sys
import requests
import json
import feedparser
import logging
import linecache
from datetime import datetime as dt
from bs4 import BeautifulSoup
from colorama import init
from threading import Thread
import time
from dateutil import tz

SPACE_ALIGNMENT = 100
TIME_FOR_BREAKING_NEWS = 60  # 1 min

logging.basicConfig(filename="NewsScraper.log", filemode="w", level=logging.ERROR)
logging.Formatter("%(asctime)s; %(levelname)s; %(message)s", "%m-%d-Y %I:%M:%S")

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())



def displayException(exception_title="", ex_type=logging.CRITICAL):
    (execution_type, execution_obj, tb) = sys.exc_info()

    f = tb.tb_frame
    ln = tb.tb_lineno
    fname = f.f_code.co_filename
    linecache.checkcache(fname)
    line = linecache.getline(fname, ln, f.f_globals)
    line_len = len(str(execution_obj)) + 10

    log_data = "{}\nTarget:  {}\nMessage: {}\nLine:    {}\n{}".format(exception_title, line.strip(), execution_obj, ln, "-" * line_len)

    if ex_type == logging.ERROR or ex_type == logging.CRITICAL:
        print("-" * line_len)
        print(exception_title)
        print("-" * line_len)

    if ex_type == logging.DEBUG:
        logger.debug(log_data)

    elif ex_type == logging.INFO:
        logger.info(log_data)

    elif ex_type == logging.WARNING:
        logger.warning(log_data)

    elif ex_type == logging.ERROR:
        logger.error(log_data)

    elif ex_type == logging.CRITICAL:
        logger.critical(log_data)



class News:
    def __init__(self):
        self.breaking = "No"
        self.headline = ""
        self.time_stamp = ""
        self.source = ""
        self.source_url = ""
        self.story = ""

    def serialize(self):
        return {
            "breaking_news": self.breaking,
            "headline": self.headline.replace("'", "<ap>"),
            "time": self.time_stamp,
            "source": self.source,
            "source url": self.source_url,
            "story": self.story.replace("'", "<ap>")
        }

class NewsParser():
    def __init__(self, url):
        self.url = url
        self.base_url = ""
        self.parsed_news = []

    def clean(self, html):
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text().replace("\xa0", " ").replace("View Full coverage on Google News", ".")
        return text.strip()
    
    def parse_feed(self):
        feeds = feedparser.parse(self.url).entries

        for feed in feeds:
            gmt_to_datetime = dt.strptime(feed.get("published", ""), "%a, %d %b %Y %H:%M:%S %Z")
            from_tz = gmt_to_datetime.replace(tzinfo=tz.tzutc())
            to_tz = from_tz.astimezone(tz.tzlocal())

            localTime = to_tz.strftime('%a, %d %b %I:%M %p')

            source = feed.get("source","").get("title", "")
            headline = self.clean(feed.get("title", "")).replace(f" - {source}", "")
            source_url = feed.get("link","")
            story = self.clean(feed.get("description",""))

            self.parsed_news.append({
                "headline": headline,
                "time": localTime,
                "source": source,
                "source url": source_url,
                "story": story
            })
        return self.parsed_news

    def parse_html(self, *xpath):

        try:
            response = requests.get(self.url)
            self.base_url = os.path.dirname(response.url)
            soup = BeautifulSoup(response.text, "html.parser")

            return soup.find_all(*xpath)

        except Exception as ex:
            displayException("Error while parsing html.", logging.DEBUG)

        return None

class NewsTicker:
    def __init__(self):
        self.news = []
        self.breaking_news_update = []
        self.connected = False
        
    def news_mapper(self, news_data):
        news = News()

        try:
            news.breaking = news_data["breaking_news"]
        except:
            news.breaking = "no"

        try:
            news.headline = news_data["headline"]
        except:
            pass

        try:    
            news.time_stamp = news_data["time"]
        except:
            news.time_stamp = dt.now().strftime('%I:%M %p')
        
        try:
            news.source = news_data["source"]
        except:
            pass
        
        try:
            news.source_url = news_data["source url"]
        except:
            pass

        try:
            news.story = news_data["story"]
        except:
            pass

        return news.serialize()

    def count(self):
        return len(self.news)

    def run_breaking_news_daemon(self):
        def _breaking_news_daemon():
            while True:
                # connect to CNN website
                breaking_news_thread = Thread(target=self.scrape_breaking_news)
                breaking_news_thread.setDaemon(True)
                breaking_news_thread.start()
                time.sleep(TIME_FOR_BREAKING_NEWS)

        # daemon thread to check breaking news from time to time
        breaking_news_thread = Thread(target=_breaking_news_daemon)
        breaking_news_thread.setDaemon(True)
        breaking_news_thread.start()

    def check_breaking_news(self):
        return len(self.breaking_news_update) > 0

    def check_latest_news(self):
        return len(self.news) > 0

    def scrape_breaking_news(self):
        breaking_news_headlines = []
        try:
            soup = NewsParser("https://cnnphilippines.com/latest")
            base_url = soup.base_url
            parsed_html = soup.parse_html("div", { "class": "breaking-news-content runtext-container"})

            # we don't get breaking news from news channel,
            # remove values of breaking news update list, to tag that we don't have new breaking news
            if parse_html is None:
                self.breaking_news_update = []
                return
            
            current_breaking_news_update = [news["headline"] for news in self.breaking_news_update]
            
            for news in parsed_html:
                for bn in news.find_all("a", { "class": "fancybox"}):
                    headline = bn.text.replace(" / ", "").strip()
                    news_data = {
                        "breaking_news": True, 
                        "headline": headline, 
                        "source": "CNN Philippines", 
                        "source url": base_url
                    }

                    mapped_news_data = self.news_mapper(news_data)
                    # if we don't have yet this headline, then append it to a temporary list of headlines
                    if not headline in current_breaking_news_update:
                        breaking_news_headlines.append(mapped_news_data)

            if len(breaking_news_headlines) > 0:
                # let's clear the contents of breaking news update list before putting the new headlines
                self.breaking_news_update = []
                self.news.extend(breaking_news_headlines)
                self.breaking_news_update.extend(breaking_news_headlines)

        except:
            displayException("Error while scraping for breaking news.", logging.DEBUG)
            pass

    def scrape_latest_news(self):
        try:
            soup = NewsParser("https://cnnphilippines.com/latest")
            base_url = soup.base_url
            parsed_html = soup.parse_html("article", {"class": "media"})

            for elem in parsed_html:
                headline = elem.find("h4").find("a").text.strip()
                source_url = base_url + elem.find("h4").find("a")["href"]
                
                paragraphs = elem.find_all("p")
                time_stamp = paragraphs[0].text.strip()
                story = paragraphs[1].text.strip()

                self.news.append({
                    "headline": headline,
                    "time": time_stamp,
                    "source": "CNN Philippines",
                    "source url": source_url,
                    "story": story
                })

        except:
            displayException("Error while scraping for latest news.", logging.DEBUG)
            pass

    def scrape_google_news(self):
        try:
            parsed_feed = NewsParser("https://news.google.com/rss?hl=en-PH&gl=PH&ceid=PH:en").parse_feed()
            # sort feed by "time" (descending order)
            feeds = sorted(parsed_feed, key=lambda feed: dt.strptime(feed["time"], "%a, %d %b %I:%M %p"), reverse=True)

            self.news.extend(feeds)

        except:
            displayException("Error while scraping for Google News.", logging.DEBUG)
            pass

    def cast_latest_news(self, meta_data=""):
        cast_news = []

        if len(self.news) < 1:
            # return immediately if no list of headlines to show
            print("\n **No new headlines found.")
            return list()
        
        for news in self.news:
            headline = news["headline"].replace("<ap>", "'").strip()
            report = f"From {news['source']}, ({news['time']}).\n\n{headline}."
            
            if meta_data:
                # filter report using meta_data keyword
                if meta_data.strip().lower() in report.lower():
                    cast_news.append(report)
            else:
                cast_news.append(report)
        
        return cast_news

    def cast_breaking_news(self):
        cast_news = []

        if len(self.breaking_news_update) < 1:
            # return immediately if no list of headlines to show
            print("\n **No new breaking news found.")
            return list()

        for news in self.breaking_news_update:
            headline = news["headline"].replace("<ap>", "'").strip()
            report = f"From {news['source']}, ({news['time']}).\n\n{headline}."
            cast_news.append(report)
        
        return cast_news

    def fetch_news(self):
        self.news = []
        cnn_soup = None
        cnn_url = ""

        print("\n Fetching information from news channels...")

        # scrape news from various websites
        self.scrape_latest_news()
        self.scrape_google_news()
        self.scrape_breaking_news()
        self.save_as_json()
        self.connected = True

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
        source = "{} {}".format(source_color, news["source url"].replace("<ap>", "'"))

        print(headline)
        print("{}more on{}".format(story, source), "\n")

    def show_news(self, isBanner=True):
        news_idx = 0
        current_news = []
        
        if len(self.news) < 1:
            # return immediately if no list of headlines to show
            print("\n No headlines found. **Check your internet connection...")
            return

        def _create_news_ticker(isBreakingNews=False):
            news_list = self.news
            window_height = "90 /NOT"

            if isBreakingNews:
                window_height = "110 /TOP"
                news_list = self.breaking_news_update
                isBreakingNews = True

            os.system(f"CMDOW @ /ren \"News Watcher\" /mov 11 -31 /siz 1550 {window_height}")

            breaking_red_color = "\033[1;37;41m"
            # connection_red_color = "\033[1;31;49m"
            color_reset = "\033[2;39;49m"

            headline = current_news["headline"].replace("<ap>", "'")
            source = current_news["source"]
            time_stamp = current_news["time"]

            formatted_headline = f"{headline} - {source} | {time_stamp} ({news_idx} of {len(news_list)})"
            ticker_detail = formatted_headline.center(168)
            deets_length = len(ticker_detail)

            counter = 0
            while True:
                os.system("cls")
                
                counter += 2
                # slice some parts of headline to make a scrolling effect
                animate_ticker_details = ticker_detail[counter:(deets_length + counter)] + ticker_detail[0:counter]
                
                print("\n")
                # if not self.connected:
                #     print(f"{connection_red_color} * No Internet Connection * {color_reset}".center(180))

                if isBreakingNews:
                    print(f"       {breaking_red_color} * BREAKING NEWS * {color_reset}".center(180))

                # headline is almost full row..
                if len(formatted_headline) > 165:
                    # let's break it into separate sentence/paragraph.
                    words = ticker_detail.split(" ")
                    half = (len(words) // 2)
                    
                    sentence = f"{' '.join(words[:half]).strip()}".center(168)
                    size = len(sentence)
                    print(f"{sentence[counter:(size + counter)] + sentence[0:counter]}")

                    sentence = f"{' '.join(words[half:]).strip()}.".center(168)
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

        while True:
            for idx, news in enumerate(self.news):

                # halt "latest news" ticker and display the breaking news
                if self.check_breaking_news() and (idx + 1) % 2 != 0:
                    for breaking_idx, breakingnews in enumerate(self.breaking_news_update):
                        news_idx = breaking_idx + 1
                        current_news = breakingnews

                        if isBanner:
                            self.create_news_banner(breakingnews)
                        else:
                            _create_news_ticker(isBreakingNews=True)         

                # continue "latest news" ticker
                news_idx = idx + 1
                current_news = news

                if isBanner:
                    self.create_news_banner(news)
                else:
                    _create_news_ticker()           
            
            os.system("cls")
            self.fetch_news()
            self.show_news(isBanner)


if __name__ == "__main__":
    news = NewsTicker()

    while True:
        os.system("cls")
        try:
            news.fetch_news()
            news.run_breaking_news_daemon()
            news.show_news(False)

        except KeyboardInterrupt:
            displayException("Keyboard Interrupt", ex_type=logging.DEBUG)
            break
        except:
            displayException("Main Exception", logging.DEBUG)
            print(" Trying to re-connect...")

        time.sleep(5)