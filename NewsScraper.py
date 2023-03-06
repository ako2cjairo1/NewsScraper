import datetime
import os
import re
import sys
import requests
import json
import feedparser
import logging
import linecache
from datetime import timedelta, datetime as dt
from bs4 import BeautifulSoup
from colorama import init
from threading import Event, Thread
import time
import tweepy
from dateutil import tz
from decouple import config


logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s", "%m-%d-%Y %I:%M:%S %p")

file_handler = logging.FileHandler("NewsScraper.log", mode="a")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)


def displayException(exception_title="", ex_type=logging.INFO):
    log_data = ""

    logger.setLevel(ex_type)
    if ex_type == logging.ERROR or ex_type == logging.CRITICAL:
        (_, message, tb) = sys.exc_info()

        f = tb.tb_frame
        lineno = tb.tb_lineno
        fname = f.f_code.co_filename.split("\\")[-1]
        linecache.checkcache(fname)
        target = linecache.getline(fname, lineno, f.f_globals)

        line_len = len(str(message)) + 10
        log_data = f"{exception_title}\n{'File:'.ljust(9)}{fname}\n{'Target:'.ljust(9)}{target.strip()}\n{'Message:'.ljust(9)}{message}\n{'Line:'.ljust(9)}{lineno}\n"
        log_data += ("-" * line_len)

    else:
        log_data = exception_title

    if ex_type == logging.DEBUG:
        logger.debug(log_data)

    elif ex_type == logging.INFO:
        logger.info(log_data)

    elif ex_type == logging.WARNING:
        logger.warning(log_data)

    elif ex_type == logging.ERROR:
        logger.error(log_data)
        raise Exception(exception_title)

    elif ex_type == logging.CRITICAL:
        logger.critical(log_data)
        raise Exception(exception_title)


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

        extract_numeric_value = [
            number for number in time_stamp.split(" ") if number.isdigit()]

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
            if value <= 0 or (day - value) <= 0:
                return (current_date_time - timedelta(hours=23, minutes=59)).strftime("%A, %d %b %Y %I:%M %p")
            else:
                return dt(year, month, (day - value), hour, minute).strftime("%A, %d %b %Y %I:%M %p")

    except Exception:
        pass
        displayException("Time stamp to date/time conversion error.")
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
        displayException("Date/Time to Time stamp conversion error.")
        return "about a moment ago"


def has_url(text):
    url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+')
    return url_pattern.search(text) is not None


def news_mapper(news_data):
    news = News()

    try:
        news.breaking = news_data["breaking_news"]
    except:
        news.breaking = "false"

    try:
        headline = news_data["headline"].replace('\"', "").replace("`", "")
        # headline = headline if has_url(
        #     headline) else f"{headline} {news_data['source url']}"

        news.headline = headline
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
        news.story = news_data["story"].replace('\"', "").replace("`", "")
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
        text = soup.get_text().replace("View Full coverage on Google News", "")
        return text.strip()

    def parse_feed(self):
        try:
            feeds = feedparser.parse(self.url).entries

            for feed in feeds:
                # gmt_to_datetime = dt.strptime(
                #     feed.get("published", ""), "%a, %d %b %Y %H:%M:%S %Z")

                # localTime = gmt_to_datetime.strftime('%A, %d %b %Y %I:%M %p')

                # +8 hours
                created_at = dt.strptime(
                    feed.get("published", ""), "%a, %d %b %Y %H:%M:%S %Z") + timedelta(hours=8)
                localTime = created_at.strftime("%A, %d %b %Y %I:%M %p")

                source = feed.get("source", "").get("title", "")
                headline = self.clean(feed.get("title", "")).replace(
                    f" - {source}", "")
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

        except Exception as ex:
            pass
            displayException(f"Error occurred while parsing rss feed. {ex}")

        return self.parsed_news

    def parse_html(self, *xpath):
        try:
            response = requests.get(self.url)
            self.base_url = os.path.dirname(response.url)

            cleaned_response = response.text.replace("\n", " ")
            soup = BeautifulSoup(cleaned_response, "html.parser")

            return soup.find_all(*xpath)

        except Exception as ex:
            pass
            displayException(f"Error occurred while parsing html. {ex}")

        return self.parsed_news


class NewsTicker:

    def __init__(self):
        self.news = []
        self.breaking_news_update = []
        self.changed_news_count = 0
        self.news_file = ""

    def count_news(self):
        return len(self.news)

    def get_news(self):
        try:
            distinct_news = []
            for news_item in self.news:
                # remove duplicates based on headlines
                if self.is_within_day(news_item["time"]) and news_item["headline"].lower() not in [news["headline"].lower() for news in distinct_news]:
                    distinct_news.append(news_item)

            # sort news by "time" (descending order - latest -> older)
            date_time_now = dt.now().strftime("%A, %d %b %Y %I:%M %p")
            return sorted(distinct_news, key=lambda feed: dt.strptime(date_time_now if feed["time"] == None else feed["time"], "%A, %d %b %Y %I:%M %p"), reverse=True)

        except Exception as ex:
            time.sleep(5)

    def run_breaking_news_daemon(self):
        def scrape_breaking_news_daemon():
            stop_event = Event()
            try:
                while not stop_event.is_set():
                    Thread(target=self.scrape_breaking_news,
                           daemon=True).start()
                    time.sleep(int(config("BREAKING_NEWS_TIMEOUT")))
                    # time.sleep(3)

            except Exception as ex:
                stop_event.set()

        Thread(target=scrape_breaking_news_daemon, daemon=True).start()

    def is_new_breaking_news(self):
        return len(self.breaking_news_update) > 0

    def check_latest_news(self):
        return self.count_news() > 0

    '''
    BREAKING NEWS Scraping
    '''

    def scrape_breaking_news(self):
        breaking_news = []

        breaking_news.extend(self.cnn_breaking_news_latest())
        breaking_news.extend(self.cnn_breaking_news_subhead())
        breaking_news.extend(self.twitter_breaking_news())

        breaking_news_headlines = []
        for bn in breaking_news:
            # remove duplicates based on headlines
            if bn["headline"].lower() not in [news["headline"].lower() for news in breaking_news_headlines]:
                breaking_news_headlines.append(bn)

        if len(breaking_news_headlines) > 0:
            # let's clear the contents of breaking news update list before putting the new headlines
            self.breaking_news_update = []
            self.news.extend(breaking_news_headlines)
            self.breaking_news_update.extend(breaking_news_headlines)

    def cnn_breaking_news_latest(self):
        breaking_news_headlines = []
        try:
            soup = NewsParser("https://cnnphilippines.com")
            parsed_html = soup.parse_html(
                "div", {"class": "breaking-news-content runtext-container"})
            base_url = soup.url

            # we didn't get any breaking news from news channel,
            # remove values of breaking_news_update list, to flag that we don't have new breaking news
            # if parsed_html is None:
            #     self.breaking_news_update = []
            #     return

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
                    if not any(headline.lower() in breaking_news["headline"].lower() for breaking_news in self.breaking_news_update) and not any(headline.lower() in breaking_news["headline"].lower() for breaking_news in self.news):
                        breaking_news_headlines.append(news_mapper(news_data))

        except Exception:
            pass
            displayException(
                "Error occurred while scraping CNN Latest Breaking News.")

        return breaking_news_headlines

    def cnn_breaking_news_subhead(self):
        breaking_news_headlines = []

        try:
            soup = NewsParser("https://cnnphilippines.com")
            teaser = soup.parse_html("div", {"class": "teaser"})
            base_url = soup.base_url

            if teaser:
                teaser = teaser[0]
                breaking_news_header = teaser.find_all(
                    "h2", {"class": "subhead-lead white-font"})
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
                                    source = teaser[0].find(
                                        "div", {"class": "author-byline"})
                                    if source:
                                        source = source.text.strip()

                                    publ_date = teaser[0].find(
                                        "div", {"class": "dateLine"})
                                    if publ_date:
                                        publ_date = publ_date.text.replace(
                                            "Published", "").strip()
                                        publ_date = convert_time_stamp_to_datetime(
                                            publ_date)
                                        # publ_date = dt.strptime(publ_date, "%b %d, %Y %I:%M:%S %p").strftime("%A, %d %b %Y %I:%M %p")

                                    news_data = {
                                        "breaking_news": "true",
                                        "headline": headline,
                                        "time": publ_date,
                                        "source": source,
                                        "source url": source_link
                                    }

                                # # if we don't have yet this headline, then append it to a temporary list of headlines
                                if self.is_within_day(publ_date) and not any(headline.lower() in breaking_news["headline"].lower() for breaking_news in self.breaking_news_update) and not any(headline.lower() in breaking_news["headline"].lower() for breaking_news in self.news):
                                    breaking_news_headlines.append(
                                        news_mapper(news_data))
        except Exception:
            pass
            displayException(
                "Error occurred while scraping CNN Breaking News Subhead.")

        return breaking_news_headlines

    def is_within_day(self, date2):
        try:
            from datetime import datetime
            if date2 == None:
                return True
            today = dt.now().strftime("%A, %d %b %Y %I:%M %p")
            # convert the strings to datetime objects
            date1 = datetime.strptime(today, "%A, %d %b %Y %I:%M %p")
            date2 = datetime.strptime(date2, "%A, %d %b %Y %I:%M %p")
            # compute the difference between the two dates
            # date_diff = date1-date2
            # convert the difference to minutes
            # minutes = int(date_diff.total_seconds() / 60)

            return True if date1.date() == date2.date() else False
        except Exception as ex:
            raise Exception(ex)

    def twitter_breaking_news(self):
        breaking_news_headlines = []
        try:
            # Creating the authentication object
            auth = tweepy.OAuthHandler(
                config("CONSUMER_KEY"), config("CONSUMER_SECRET"))
            # Setting your access token and secret
            auth.set_access_token(config("ACCESS_TOKEN"),
                                  config("ACCESS_TOKEN_SECRET"))
            # Creating the API object while passing in the auth information
            api = tweepy.API(auth)

            def _get_tweets(tweets, isBreakingNews=False):
                for tweet in tweets:
                    created_at = tweet.created_at.strftime(
                        "%A, %d %b %Y %I:%M %p")
                    # +8 hours
                    created_at = dt.strptime(
                        created_at, "%A, %d %b %Y %I:%M %p") + timedelta(hours=8)

                    created_at = created_at.strftime("%A, %d %b %Y %I:%M %p")

                    # filter tweets that was created today
                    if self.is_within_day(created_at) and (isBreakingNews or ("breaking news" in tweet.full_text.lower() or "breaking:" in tweet.full_text.lower() or "just in:" in tweet.full_text.lower())):
                        headline = tweet.full_text.replace(
                            "BREAKING:", "").replace("BREAKING NEWS:", "").strip()

                        news_data = {
                            "breaking_news": "true",
                            "headline": headline,
                            "time": created_at,
                            "source": tweet.user.name,
                            "source url": f"https://twitter.com/i/web/status/{tweet.id}"
                        }

                        # if we don't have yet this headline, then append it to a temporary list of headlines
                        if not any(headline.lower() in breaking_news["headline"].lower() for breaking_news in self.breaking_news_update) and not any(headline.lower() in breaking_news["headline"].lower() for breaking_news in self.news):
                            breaking_news_headlines.append(
                                news_mapper(news_data))

            for source in {"BBCBreaking", "breakingnews",
                           "CNNBreaking", "cnnbrk"}:
                try:
                    result = api.user_timeline(
                        id=source, count=10, tweet_mode="extended")
                    _get_tweets(result, True)
                except Exception:
                    continue

            for source in {"CNN", "NBCNews", "ABC", "CBSNews", "FoxNews", "nytimes", "washingtonpost", "Reuters", "AP",
                           "ABSCBNNews", "gmanews", "philstar", "inquirerdotnet", "rapplerdotcom", "cnnphilippines", "inquirerdotnet", "bworldph"}:
                try:
                    # if api.get_user(source).verified:
                    result = api.user_timeline(
                        id=source, count=20, tweet_mode="extended")
                    _get_tweets(result)
                except Exception:
                    continue

        except Exception:
            pass
            print("Error occurred while scraping Twitter Breaking News.")
        return breaking_news_headlines

    '''
    lATEST NEWS Scraping
    '''

    def scrape_latest_news(self):
        latest_news = []
        latest_news.extend(self.cnn_news_latest())
        latest_news.extend(self.google_news_latest())

        for news_item in latest_news:
            self.news.append(news_item)

    def cnn_news_latest(self):
        latest_news = []
        try:
            soup = NewsParser("https://cnnphilippines.com/latest")
            parsed_html = soup.parse_html("article", {"class": "media"})
            base_url = soup.base_url

            for elem in parsed_html:
                headline = elem.find("h4").find(
                    "a").text.replace("\xa0", " ").strip()

                # don't append if we already have this headline in the list
                if not any(headline.lower() in hl["headline"].lower() for hl in self.news):
                    paragraphs = elem.find_all("p")
                    time_stamp = convert_time_stamp_to_datetime(
                        paragraphs[0].text.strip())

                    # check if the news time is within 24hrs
                    if self.is_within_day(time_stamp):
                        source_url = base_url + \
                            elem.find("h4").find("a")["href"]
                        story = paragraphs[1].text.strip()

                        news_data = {
                            "headline": headline,
                            "time": time_stamp,
                            "source": "CNN Philippines",
                            "source url": source_url,
                            "story": story
                        }
                        latest_news.append(news_mapper(news_data))

        except Exception as ex:
            pass
            displayException(
                f"CNN latest news website is not in correct format. {ex}")

        return latest_news

    def google_news_latest(self):
        latest_news_feed = []
        try:
            parser = NewsParser(
                "https://news.google.com/rss?hl=en-PH&gl=PH&ceid=PH:en")
            latest_news_feed = parser.parse_feed()

        except Exception as ex:
            pass
            displayException(
                f"Google News Feed is not in correct format. {ex}")

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
                headline = news["headline"]
                source = news['source']
                is_breaking = news['breaking_news']
                time_stamp = convert_datetime_to_time_stamp(news['time'])

                report = f"From {source} ({time_stamp}).\n\n{headline}."

                if headline and meta_data:
                    # filter news report using meta_data keyword found in "headline" and "story" section
                    if is_match(meta_data.lower(), (headline.split(" ") + source.split(" "))):
                        cast_news.append(
                            {"headline": headline, "report": report, "breaking_news": is_breaking, "source url": news["source url"]})
                elif headline:
                    cast_news.append(
                        {"headline": headline, "report": report, "breaking_news": is_breaking, "source url": news["source url"]})

        except Exception:
            pass
            displayException("Error occurred while casting latest news.")

        return cast_news

    def cast_breaking_news(self, on_demand=False):
        cast_news = []
        news_updates = self.breaking_news_update

        try:
            if on_demand:
                news_updates = [news for news in self.get_news(
                ) if news["breaking_news"].lower() == "true"]
            elif len(news_updates) < 1:
                # return immediately if no list of headlines to show
                return list()

            for news in news_updates:
                headline = news["headline"].strip()
                source = news['source']
                time_stamp = convert_datetime_to_time_stamp(news["time"])

                report = f"From {source} ({time_stamp}).\n\n{headline}."

                # Author is present in source, let's remove the "From" prefix of our report
                if "By " in source:
                    report = report.replace("From ", "")

                # make sure the headline is not blank when we add it on the list
                if headline:
                    # cast_news.append(report)
                    cast_news.append(
                        {"headline": headline, "report": report, "source url": news["source url"]})

        except Exception:
            pass
            displayException("Error occurred while casting breaking news.")

        return cast_news

    def fetch_news(self, news_file=""):
        date_now = dt.now().strftime('%A, %d %b %Y')
        self.news_file = f"{config('NEWS_DIR')}/News/News-{date_now}.json"

        if news_file:
            self.news_file = news_file

        try:
            def _save_as_json():
                # create the list of news as json type file
                with open(self.news_file, "w", encoding="utf-8") as fw:
                    news = {
                        "news": self.get_news()
                    }
                    fw.write(json.dumps(news, indent=4,
                             sort_keys=True, ensure_ascii=False))

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

        except Exception as ex:
            pass
            displayException(
                f"Error occurred while fetching news. {ex}", logging.CRITICAL)

    def load_news_from_json(self):
        try:
            date_now = dt.now().strftime("%A, %d %b %Y")

            if self.count_news() == 0 and os.path.isfile(self.news_file):
                # create the list of news as json type file
                with open(self.news_file, "r", encoding="utf-8") as fw:
                    news = json.load(fw)
                    self.news = [news for news in news["news"] if dt.strptime(
                        news["time"], "%A, %d %b %Y %I:%M %p").strftime("%A, %d %b %Y") == date_now]
                    # let's remember the number of news from json that we loaded.
                    # this will be our reference if there are changes/additional news where discovered/scraped
                    self.changed_news_count = self.count_news()

                # for breaking_news in self.news:
                #     # if we don't have yet this headline, then append it to a temporary list of headlines
                #     if breaking_news["breaking_news"] == "true" and dt.strptime(breaking_news["time"], "%A, %d %b %Y %I:%M %p").strftime("%A, %d %b %Y") == date_now and not any(breaking_news["headline"] in news["headline"].lower() for news in self.breaking_news_update):
                #         self.breaking_news_update.append(breaking_news)
        except Exception:
            pass
            displayException("Error occurred while loading news from file.")

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

            os.system(
                f"CMDOW @ /ren \"News Watcher\" /mov 11 -31 /siz 1550 {window_height}")

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
                os.system("clear")

                counter += 2
                # slice some parts of headline to make a scrolling effect
                animate_ticker_details = ticker_detail[counter:(
                    deets_length + counter)] + ticker_detail[0:counter]

                print("\n")
                if isBreakingNews:
                    print(
                        f"       {breaking_red_color} * BREAKING NEWS * {color_reset}".center(180))

                # headline is almost full row..
                if len(formatted_headline) > 165:
                    # let's break it into separate sentence/paragraph.
                    words = ticker_detail.split(" ")
                    half = (len(words) // 2)

                    sentence = f"{' '.join(words[:half]).strip()}".center(168)
                    size = len(sentence)
                    print(
                        f"{sentence[counter:(size + counter)] + sentence[0:counter]}")

                    sentence = f"{' '.join(words[half:]).strip()}.".center(168)
                    size = len(sentence)
                    print(
                        f"{sentence[counter:(size + counter)] + sentence[0:counter]}")

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
                if self.is_new_breaking_news() and (idx + 1) % 2 != 0:
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

            os.system("clear")
            print("\nFetching information from news channels...", end="")
            self.fetch_news()
            self.show_news(isBanner)


if __name__ == "__main__":
    news = NewsTicker()
    os.system("clear")

    while True:
        try:
            print("\nFetching information from news channels...", end="")
            news.fetch_news()
            news.run_breaking_news_daemon()
            news.show_news(False)

        except KeyboardInterrupt:
            pass
            displayException("Keyboard Interrupt", ex_type=logging.DEBUG)
            break
        except Exception:
            pass
            displayException("NewsTicker Main Exception")
            print(" Trying to re-connect...")

        time.sleep(5)
