from urllib.request import urlopen

from lxml.html import parse


class HtmlParser:
    def __init__(self, url: str):
        self.url = url
        self.page = parse(urlopen(url)).getroot()

    @property
    def xpath(self):
        return self.page.xpath
