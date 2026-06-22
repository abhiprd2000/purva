from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen, Request
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from .base import Collector, Document


class NewsCollector(Collector):
    name = "news"

    def __init__(
        self,
        source_name: str,
        section_urls: list[str],
        link_selector: str,
        content_selector: str,
        user_agent: str,
        request_delay: float = 2.0,
        max_articles: int = 40,
        timeout: float = 20.0,
        respect_robots: bool = True,
    ):
        self.name = source_name
        self.section_urls = section_urls
        self.link_selector = link_selector
        self.content_selector = content_selector
        self.request_delay = request_delay
        self.max_articles = max_articles
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _robots_for(self, root: str):
        if root in self._robots:
            return self._robots[root]
        rp = urllib.robotparser.RobotFileParser()
        robots_url = urljoin(root, "/robots.txt")
        try:
            req = Request(robots_url, headers={"User-Agent": self.session.headers["User-Agent"]})
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
            rp.parse(body.splitlines())
        except Exception as e:
            print(f"  [robots] could not read {robots_url} ({e}); proceeding without restriction")
            rp = None
        self._robots[root] = rp
        return rp

    def _allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots_for(root)
        if rp is None:
            return True
        return rp.can_fetch(self.session.headers["User-Agent"], url)

    def _get(self, url: str) -> str | None:
        if not self._allowed(url):
            print(f"  [robots] disallowed by site policy: {url}")
            return None
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [http] {e} :: {url}")
            return None
        finally:
            time.sleep(self.request_delay)
        resp.encoding = resp.apparent_encoding or resp.encoding
        return resp.text

    def _article_links(self, listing_html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(listing_html, "lxml")
        links = []
        for a in soup.select(self.link_selector):
            href = a.get("href")
            if href:
                links.append(urljoin(base_url, href))
        return list(dict.fromkeys(links))

    def _article_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        nodes = soup.select(self.content_selector)
        return "\n".join(n.get_text(separator=" ", strip=True) for n in nodes)

    def iter_documents(self) -> Iterator[Document]:
        seen_articles: set[str] = set()
        fetched = 0
        for section in self.section_urls:
            listing = self._get(section)
            if not listing:
                continue
            found = self._article_links(listing, section)
            print(f"  [links] {len(found)} article links on {section}")
            for link in found:
                if fetched >= self.max_articles:
                    return
                if link in seen_articles:
                    continue
                seen_articles.add(link)
                html = self._get(link)
                if not html:
                    continue
                text = self._article_text(html)
                if text.strip():
                    fetched += 1
                    print(f"  [ok] article {fetched}: {link}")
                    yield Document(url=link, text=text, meta={"source": self.name})
                else:
                    print(f"  [empty] no text via content_selector: {link}")