import os
import sys
import requests
import json
from datetime import timedelta, datetime as dt
from bs4 import BeautifulSoup
import time


class FunHoliday:

    def parser(self, url):
        response = requests.get(url)
        # os.path.dirname(response.url)
        soup = BeautifulSoup(response.text, "html.parser")
        return soup, response.url

    def convert_to_eng_month_name(self, date):
        swither = {
            "Ene": "Jan",
            "Peb": "Feb",
            "Mar": "Mar",
            "Abr": "Apr",
            "May": "May",
            "Hun": "Jun",
            "Hul": "Jul",
            "Ago": "Aug",
            "Set": "Sep",
            "Oct": "Oct",
            "Nob": "Nov",
            "Dis": "Dec"
        }

        temp_date = date.split(" ")
        day = temp_date[0].zfill(2)
        month_name = temp_date[1]

        translation = swither.get(month_name, "")
        converted_month_name = f"{day} {translation}"  # date.replace(month_name, translation)
        return converted_month_name

    def get_fun_holiday(self):
        fun_holiday_result = {"success": "false", "holiday": list()}
        date_now = dt.now().strftime("%d %b")

        try:
            soup, base_url = self.parser("https://www.timeanddate.com/holidays/fun/")
            holidays = soup.find_all("tr")

            for holiday in holidays:
                table_header_tag = holiday.find_all("th")
                anchor_tag = holiday.find("a")

                if table_header_tag and anchor_tag:
                    date = table_header_tag[0].text

                    if self.convert_to_eng_month_name(date) == date_now:
                        holiday_name = anchor_tag.text
                        source_url = f"{base_url}{anchor_tag['href'].split('/')[-1]}"

                        # let's extract contents of articles based on source_url we got
                        args = self.parser(source_url)
                        # select the contents of article
                        article = args[0].select("div", {"class": "article__body"})

                        # extract all paragraphs
                        paragraph_tag = article[0].find_all("p")
                        # index 1 is expected to be the heading of article
                        main_heading = paragraph_tag[1].text

                        # find paragraph(s) that starts with (…)
                        # this will be the "did you know" content
                        did_you_know = ""
                        for item in paragraph_tag:
                            if "…" in item.text or "..." in item.text:
                                did_you_know = item.text
                                break

                        holiday = {
                            "date": self.convert_to_eng_month_name(date),
                            "title": holiday_name,
                            "heading": main_heading,
                            "did you know": did_you_know,
                            "source url": source_url
                        }
                        return {"success": "true", "holiday": holiday}

            return fun_holiday_result

        except Exception as ex:
            return {"success": "false", "message": str(ex)}


if __name__ == "__main__":
    fh = FunHoliday()
    
    result = fh.get_fun_holiday()

    if result["success"] == "true":
        holiday = result["holiday"]

        title = f'Today is \"{holiday["title"]}\"'
        message = holiday["heading"]

        print(title, message)
