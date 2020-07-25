import os
import sys
import requests
import json
import feedparser
import logging
import linecache
from datetime import timedelta, datetime as dt
from bs4 import BeautifulSoup
from colorama import init
from threading import Thread
import time
from dateutil import tz


SPACE_ALIGNMENT = 100
TIME_FOR_BREAKING_NEWS = 60  # 1 min

logging.basicConfig(filename="NewsScraper.log", filemode="w", level=logging.ERROR, format="%(asctime)s; %(levelname)s; %(message)s")
# logging.Formatter("%(asctime)s; %(levelname)s; %(message)s", "%m-%d-Y %I:%M:%S")

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def displayException(exception_title="", ex_type=logging.CRITICAL):
    (execution_type, message, tb) = sys.exc_info()

    f = tb.tb_frame
    lineno = tb.tb_lineno
    fname = f.f_code.co_filename
    linecache.checkcache(fname)
    target = linecache.getline(fname, lineno, f.f_globals)
    # line_len = len(str(message)) + 10
    log_data = "{}\nFile:  {}\nTarget:  {}\nMessage: {}\nLine:    {}".format(fname, exception_title, target.strip(), message, lineno)

    if ex_type == logging.ERROR or ex_type == logging.CRITICAL:
        print("-" * 23)
        print(exception_title)
        print("-" * 23)

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


def convert_time_stamp_to_datetime(time_stamp):
    current_date_time = dt.now()

    try:
        if "about Just now" in time_stamp:
            return current_date_time.strftime("%A, %d %b %Y %I:%M %p")

        year = current_date_time.year
        month = current_date_time.month
        day = current_date_time.day
        hour = current_date_time.hour
        minute = current_date_time.minute

        extract_numeric_value = [number for number in time_stamp.split(" ") if number.isdigit()]

        if len(extract_numeric_value) > 0:
            value = int(extract_numeric_value[0])
        else:
            value = 0

        if "mins" in time_stamp:
            if value <= 0:
                return current_date_time.strftime("%A, %d %b %Y %I:%M %p")
            else:
                return (current_date_time - timedelta(minutes=value)).strftime("%A, %d %b %Y %I:%M %p")
        elif "hour" in time_stamp:
            if value <= 0:
                return (current_date_time - timedelta(minutes=59)).strftime("%A, %d %b %Y %I:%M %p")
            else:
                return (current_date_time - timedelta(hours=value)).strftime("%A, %d %b %Y %I:%M %p")
        else:  # day
            if value <= 0:
                return (current_date_time - timedelta(hours=23, minutes=59)).strftime("%A, %d %b %Y %I:%M %p")
            else:
                return dt(year, month, (day - value), hour, minute).strftime("%A, %d %b %Y %I:%M %p")

    except Exception:
        pass
        displayException("Time stamp to date/time conversion error.", logging.ERROR)
        return current_date_time.strftime("%A, %d %b %Y %I:%M %p")


def convert_datetime_to_time_stamp(date_time):
    try:
        current_date_time = dt.now()
        if date_time == None:
            date_time = current_date_time

        parsed_date_time = dt.strptime(date_time, "%A, %d %b %Y %I:%M %p")
        time_diff = (current_date_time - parsed_date_time)

        sec_diff = time_diff.seconds
        min_diff = sec_diff // 60
        hour_diff = min_diff // 60

        if time_diff.days > 0:
            return f"about {time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
        elif hour_diff > 0:
            return f"about {hour_diff} hour{'s' if hour_diff > 1 else ''} ago"
        elif min_diff > 0:
            return f"about {min_diff} min{'s' if min_diff > 1 else ''} ago"
        else:
            return "about Just now"

    except Exception:
        pass
        displayException("Date/Time to Time stamp conversion error.", logging.ERROR)
        return "about a moment ago"


def news_mapper(news_data):
    news = News()

    try:
        news.breaking = news_data["breaking_news"]
    except:
        news.breaking = "false"

    try:
        news.headline = news_data["headline"]
    except:
        pass

    datetime_now = dt.now().strftime("%A, %d %b %Y %I:%M %p")
    try:
        news.time_stamp = news_data["time"] if news_data["time"] else datetime_now
    except:
        pass
        news.time_stamp = datetime_now

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


def is_match(voice_data, keywords):
    lowercase_keywords = [keyword.lower().strip() for keyword in keywords]

    if len(voice_data.split(" ")) > 1:
        if voice_data.lower() in " ".join(lowercase_keywords):
            return True
    else:
        if (any(map(lambda word: word == voice_data.lower(), lowercase_keywords))):
            return True
    return False


class News:

    def __init__(self):
        self.breaking = "false"
        self.headline = ""
        self.time_stamp = ""
        self.source = ""
        self.source_url = ""
        self.story = ""

    def serialize(self):
        return {
            "breaking_news": self.breaking,
            "headline": self.headline,
            "time": self.time_stamp,
            "source": self.source,
            "source url": self.source_url,
            "story": self.story
        }


class NewsParser():

    def __init__(self, url):
        self.url = url
        self.base_url = ""
        self.parsed_news = []

    def clean(self, html):
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text().replace("\n", " ").replace("\xa0", " ").replace("\u2013", "-").replace("View Full coverage on Google News", "")
        return text.strip()

    def parse_feed(self):
        try:
            feeds = feedparser.parse(self.url).entries

            for feed in feeds:
                gmt_to_datetime = dt.strptime(feed.get("published", ""), "%a, %d %b %Y %H:%M:%S %Z")
                from_tz = gmt_to_datetime.replace(tzinfo=tz.tzutc())
                to_tz = from_tz.astimezone(tz.tzlocal())

                localTime = to_tz.strftime('%A, %d %b %Y %I:%M %p')

                source = feed.get("source", "").get("title", "")
                headline = self.clean(feed.get("title", "")).replace(f" - {source}", "")
                source_url = feed.get("link", "")
                story = self.clean(feed.get("description", ""))

                news_data = {
                    "headline": headline,
                    "time": localTime,
                    "source": source,
                    "source url": source_url,
                    "story": story
                }
                self.parsed_news.append(news_mapper(news_data))

        except Exception:
            pass
            displayException("Error while parsing rss feed.", logging.ERROR)

        return self.parsed_news

    def parse_html(self, *xpath):
        try:
            response = requests.get(self.url)
            self.base_url = os.path.dirname(response.url)

            cleaned_response = response.text.replace("\n", " ")
            soup = BeautifulSoup(cleaned_response, "html.parser")

            return soup.find_all(*xpath)

        except Exception:
            pass
            displayException("Error while parsing html.", logging.ERROR)

        return self.parsed_news


class NewsTicker:

    def __init__(self):
        date_now = dt.now().strftime('%A, %d %b %Y')
        self.news = []
        self.breaking_news_update = []
        self.changed_news_count = 0
        self.news_file = f"News-{date_now}.json"

    def count_news(self):
        return len(self.news)

    def get_news(self):
        # sort news by "time" (descending order - latest -> older)
        date_time_now = dt.now().strftime("%A, %d %b %Y %I:%M %p")
        return sorted(self.news, key=lambda feed: dt.strptime(date_time_now if feed["time"] == None else feed["time"], "%A, %d %b %Y %I:%M %p"), reverse=True)

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
        return self.count_news() > 0

    '''
    BREAKING NEWS Scraping
    '''

    def scrape_breaking_news(self):
        breaking_news_headlines = []

        breaking_news_headlines.extend(self.cnn_breaking_news_latest())
        breaking_news_headlines.extend(self.cnn_breaking_news_subhead())

        if len(breaking_news_headlines) > 0:
            # let's clear the contents of breaking news update list before putting the new headlines
            self.breaking_news_update = []
            self.news.extend(breaking_news_headlines)
            self.breaking_news_update.extend(breaking_news_headlines)

    def cnn_breaking_news_latest(self):
        breaking_news_headlines = []
        try:
            soup = NewsParser("https://cnnphilippines.com")
            parsed_html = soup.parse_html("div", {"class": "breaking-news-content runtext-container"})
            base_url = soup.base_url

            # we didn't get any breaking news from news channel,
            # remove values of breaking_news_update list, to flag that we don't have new breaking news
            if parsed_html is None:
                self.breaking_news_update = []
                return

            for news in parsed_html:
                for bn in news.find_all("a", {"class": "fancybox"}):
                    headline = bn.text.replace(" / ", "").strip()
                    news_data = {
                        "breaking_news": "true",
                        "headline": headline,
                        "source": "CNN Philippines",
                        "source url": base_url
                    }
                    # if we don't have yet this headline, then append it to a temporary list of headlines
                    # if not (headline.lower() in [news["headline"].lower() for news in self.breaking_news_update]) and not (headline.lower() in [news["headline"].lower() for news in self.news]):
                    if not is_match(headline, [latest_news["headline"] for latest_news in self.breaking_news_update]) and not is_match(headline, [news["headline"] for news in self.news]):
                        breaking_news_headlines.append(news_mapper(news_data))

        except Exception:
            pass
            displayException("Error while scraping CNN Latest Breaking News.", logging.ERROR)

        return breaking_news_headlines

    def cnn_breaking_news_subhead(self):
        breaking_news_headlines = []

        try:
            soup = NewsParser("https://cnnphilippines.com")
            teaser = soup.parse_html("div", {"class": "teaser"})
            base_url = soup.base_url

            if teaser:
                teaser = teaser[0]
                breaking_news_header = teaser.find_all("h2", {"class": "subhead-lead white-font"})
                if breaking_news_header:
                    breaking_news_header = breaking_news_header[0].text

                    # if we frind breaking news header, let's try to extract the source link.
                    if "BREAKING NEWS" in breaking_news_header.strip().upper():
                        source_link = teaser.find("a")
                        if source_link:
                            source_link = base_url + source_link["href"]

                            # parse report using source_link we found
                            soup = NewsParser(source_link)
                            teaser = soup.parse_html("article", {"class": ""})

                            headline = ""
                            source = ""
                            publ_date = ""
                            if teaser:
                                headline = teaser[0].find("h1")
                                if headline:
                                    headline = headline.text.strip()

                                source = teaser[0].find("div", {"class": "author-byline"})
                                if source:
                                    source = source.text.strip()

                                publ_date = teaser[0].find("div", {"class": "dateLine"})
                                if publ_date:
                                    publ_date = publ_date.text.replace("Published", "").strip()
                                    publ_date = dt.strptime(publ_date, "%b %d, %Y %I:%M:%S %p").strftime("%A, %d %b %Y %I:%M %p")

                                news_data = {
                                    "breaking_news": "true",
                                    "headline": headline,
                                    "time": publ_date,
                                    "source": source,
                                    "source url": source_link
                                }

                                # if we don't have yet this headline, then append it to a temporary list of headlines
                                # if not (headline.lower() in [news["headline"].lower() for news in self.breaking_news_update]) and not (headline.lower() in [news["headline"].lower() for news in self.news]):
                                if not is_match(headline, [latest_news["headline"] for latest_news in self.breaking_news_update]) and not is_match(headline, [news["headline"] for news in self.news]):
                                    breaking_news_headlines.append(news_mapper(news_data))
        except Exception:
            pass
            displayException("Error while scraping CNN Breaking News Subhead.", logging.ERROR)

        return breaking_news_headlines

    '''
    lATEST NEWS Scraping
    '''

    def scrape_latest_news(self):
        consolidated = []
        consolidated.extend(self.cnn_news_latest())
        consolidated.extend(self.google_news_latest())

        for news in consolidated:
            # if we don't have yet this headline, then append it to a temporary list of headlines
            # if not any(news["headline"].lower() in latest_news["headline"].lower() for latest_news in self.news):
            if not is_match(news["headline"], [latest_news["headline"] for latest_news in self.news]):
                self.news.append(news)

    def cnn_news_latest(self):
        latest_news = []
        try:
            soup = NewsParser("https://cnnphilippines.com/latest")
            parsed_html = soup.parse_html("article", {"class": "media"})
            base_url = soup.base_url

            for elem in parsed_html:
                headline = elem.find("h4").find("a").text.replace("\xa0", " ").strip()

                # don't append if we already have this headline in the list
                if not any(headline.lower() in hl["headline"].lower() for hl in self.news):
                    paragraphs = elem.find_all("p")
                    time_stamp = convert_time_stamp_to_datetime(paragraphs[0].text.strip())
                    source_url = base_url + elem.find("h4").find("a")["href"]
                    story = paragraphs[1].text.strip()

                    news_data = {
                        "headline": headline,
                        "time": time_stamp,
                        "source": "CNN Philippines",
                        "source url": source_url,
                        "story": story
                    }
                    latest_news.append(news_mapper(news_data))

        except Exception:
            pass
            displayException("CNN latest news website is not in correct format.", logging.ERROR)

        return latest_news

    def google_news_latest(self):
        latest_news_feed = []
        try:
            parser = NewsParser("https://news.google.com/rss?hl=en-PH&gl=PH&ceid=PH:en")
            latest_news_feed = parser.parse_feed()

        except Exception:
            pass
            displayException("Google News Feed is not in correct format.", logging.ERROR)

        return latest_news_feed

    '''
    News Reporting (formatted)
    '''

    def cast_latest_news(self, meta_data=""):
        cast_news = []

        try:
            if self.count_news() < 1:
                # return immediately if no list of headlines to show
                print("\n **No new headlines found.")
                return list()

            for news in self.get_news():
                headline = news["headline"].strip()
                time_stamp = convert_datetime_to_time_stamp(news['time'])

                report = f"From {news['source']}, ({time_stamp}).\n {headline}."

                if meta_data:
                    # filter news report using meta_data keyword found in "headline" and "story" section
                    if is_match(meta_data, report.split(" ")):
                        cast_news.append({"report": report, "source url": news["source url"]})
                else:
                    cast_news.append({"report": report, "source url": news["source url"]})

        except Exception:
            displayException("Error occurred while casting latest news.", logging.ERROR)

        return cast_news

    def cast_breaking_news(self):
        cast_news = []

        try:
            if len(self.breaking_news_update) < 1:
                # return immediately if no list of headlines to show
                print("\n **No new breaking news found.")
                return list()

            for news in self.breaking_news_update:
                headline = news["headline"].strip()
                time_stamp = convert_datetime_to_time_stamp(news["time"])

                source = news['source']
                report = f"From {source}, ({time_stamp}).\n {headline}."

                # Author is present in source, let's remove the "From" prefix of our report
                if "By " in source:
                    report = report.replace("From ", "")

                cast_news.append(report)

        except Exception:
            displayException("Error occurred while casting breaking news.", logging.ERROR)

        return cast_news

    def fetch_news(self, news_file=""):
        if news_file:
            self.news_file = news_file

        try:
            def _save_as_json():
                # create the list of news as json type file
                with open(self.news_file, "w", encoding="utf-8") as fw:
                    news = {
                        "news": self.get_news()
                    }
                    fw.write(json.dumps(news, indent=4, sort_keys=True))

            self.load_news_from_json()
            # scrape news from various websites
            self.scrape_breaking_news()
            self.scrape_latest_news()

            # there are changes
            if self.changed_news_count == 0 or (self.count_news() != self.changed_news_count):
                # save the scraped news to json file
                _save_as_json()
                # let's remember the number of news from json that we loaded.
                # this will be our reference if there are changes/additional news where discovered/scraped
                self.changed_news_count = self.count_news()

        except Exception:
            pass
            displayException("Error occurred while fetching news.", logging.CRITICAL)

    def load_news_from_json(self):
        date_now = dt.now().strftime("%A, %d %b %Y")

        if self.count_news() == 0 and os.path.isfile(self.news_file):
            # create the list of news as json type file
            with open(self.news_file, "r", encoding="utf-8") as fw:
                news = json.load(fw)
                self.news = [news for news in news["news"] if dt.strptime(news["time"], "%A, %d %b %Y %I:%M %p").strftime("%A, %d %b %Y") == date_now]
                # let's remember the number of news from json that we loaded.
                # this will be our reference if there are changes/additional news where discovered/scraped
                self.changed_news_count = self.count_news()

            for breaking_news in self.news:
                # if we don't have yet this headline, then append it to a temporary list of headlines
                if breaking_news["breaking_news"] == "true" and dt.strptime(breaking_news["time"], "%A, %d %b %Y %I:%M %p").strftime("%A, %d %b %Y") == date_now and not any(breaking_news["headline"] in news["headline"].lower() for news in self.breaking_news_update):
                    self.breaking_news_update.append(breaking_news)

    def create_news_banner(self, news):
        title_color = "\033[2;30;47m"
        source_color = "\033[1;36;49m"
        color_reset = "\033[0;39;49m"

        headline = "{} {} ".format(title_color, news["headline"])
        story = "{} {} ".format(color_reset, news["story"])
        source = "{} {}".format(source_color, news["source url"])

        print(headline)
        print("{}more on{}".format(story, source), "\n")

    def show_news(self, isBanner=True):
        news_idx = 0
        current_news = []

        if self.count_news() < 1:
            # return immediately if no list of headlines to show
            print("\n No headlines found. **Check your internet connection...")
            return

        top_50_latest_news = self.get_news()
        if len(top_50_latest_news) > 50:
            top_50_latest_news = top_50_latest_news[:50]

        def _create_news_ticker(isBreakingNews=False):
            news_list = top_50_latest_news
            window_height = "90 /NOT"

            if isBreakingNews:
                window_height = "110 /TOP"
                news_list = self.breaking_news_update
                isBreakingNews = True

            os.system(f"CMDOW @ /ren \"News Watcher\" /mov 11 -31 /siz 1550 {window_height}")

            breaking_red_color = "\033[1;37;41m"
            # connection_red_color = "\033[1;31;49m"
            color_reset = "\033[2;39;49m"

            headline = current_news["headline"]
            source = current_news["source"]
            time_stamp = convert_datetime_to_time_stamp(current_news["time"])

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
            for idx, news in enumerate(top_50_latest_news):

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
            print("\nFetching information from news channels...")
            self.fetch_news()
            self.show_news(isBanner)


if __name__ == "__main__":
    news = NewsTicker()

    while True:
        os.system("cls")
        try:
            print("\nFetching information from news channels...")
            news.fetch_news()
            news.run_breaking_news_daemon()
            news.show_news(False)

        except KeyboardInterrupt:
            displayException("Keyboard Interrupt", ex_type=logging.DEBUG)
            break
        except Exception:
            pass
            displayException("Main Exception", logging.CRITICAL)
            print(" Trying to re-connect...")

        time.sleep(5)
