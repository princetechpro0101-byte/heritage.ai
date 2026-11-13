"""
Project: HeritageAI — Global Cultural Heritage Scholarships
Project Owner: Dr. Noel Biseko Lwoga
Contact: noelight79@gmail.com | 0784756363
Module: Live Internet Search + RSS + Direct Scrapers + Groq AI Extractor
"""

import os
import json
import time
import requests
import feedparser
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from ddgs import DDGS
from groq import Groq

# 1. LIVE GLOBAL INTERNET SEARCH QUERIES
LIVE_SEARCH_QUERIES = [
    "cultural heritage scholarship fellowship open applications",
    "archaeology museum studies grant scholarship international",
    "UNESCO ICCROM ICOM heritage conservation fellowship apply",
    "world heritage management PhD masters scholarship funded",
    "historic preservation cultural conservation grant open"
]

# 2. GLOBAL RSS & GOOGLE NEWS FEEDS
RSS_FEEDS = [
    "https://unesco.org",
    "https://iccrom.org",
    "https://icom.museum",
    "https://google.com",
    "https://google.com"
]

# 3. DIRECT HERITAGE INSTITUTIONS & UNIVERSITY DEPARTMENTS
DIRECT_WEB_SOURCES = [
    "https://getty.edu",
    "https://iccrom.org",
    "https://unesco.org",
    "https://wmf.org",
    "https://awhf.net",
    "https://si.edu",
    "https://wennergren.org",
    "https://ox.ac.uk",
    "https://ucl.ac.uk"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

HERITAGE_IMAGES = [
    "https://unsplash.com",
    "https://unsplash.com",
    "https://unsplash.com",
    "https://unsplash.com"
]

def extract_images(soup, base_url):
    """Finds real photos from the webpage."""
    urls = []
    for img in soup.find_all('img', src=True):
        src = img['src']
        if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            full_url = urljoin(base_url, src)
            if not any(skip in full_url.lower() for skip in ['logo', 'icon', 'avatar', 'spinner', 'pixel']):
                urls.append(full_url)
    return urls[:6]

def fetch_page_content(url):
    """Downloads a webpage and cleans its text and images."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        images = extract_images(soup, url)
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        clean_text = soup.get_text(separator=' ', strip=True)
        return clean_text, images
    except Exception:
        return "", []

def analyze_with_groq(source_url, raw_text, available_images):
    """Uses Groq AI (Llama 3.3 70B) safely to extract active/ongoing scholarships."""
    if not raw_text or len(raw_text) < 150:
        return []

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[AI Warning] GROQ_API_KEY is not set in environment variables.")
        return []

    client = Groq(api_key=api_key)

    prompt = f"""
    You are an expert global scholarship researcher for HeritageAI (Owned by Dr. Noel Biseko Lwoga).
    Analyze the webpage content below from: {source_url}

    Extract ONLY active, ongoing, or upcoming scholarships, fellowships, research grants, or funded training programs in:
    - Cultural Heritage, Conservation & Historic Preservation
    - Archaeology, Anthropology & Paleontology
    - Museum Studies, Curatorial Work & Archival Science
    - World Heritage Site Management

    Ignore expired programs from past years.
    Return ONLY a valid JSON array of objects with these exact keys:
    - "title": Official title of the scholarship/fellowship
    - "organization": Host university, museum, or heritage body
    - "location": Exact City and Country (or "Global / International")
    - "image_url": Pick the best photo URL from {available_images} or use "{HERITAGE_IMAGES}"
    - "summary": 2-sentence summary of who can apply and what is funded
    - "full_details": Detailed eligibility, funding coverage (tuition, travel, stipend), and application instructions
    - "contact_email": Official contact email found in text (or "See official portal")
    - "contact_phone": Official phone number found in text (or "Not listed")
    - "apply_url": Direct URL to the opportunity (use "{source_url}")
    - "deadline": Application deadline date (or "Ongoing / Check Official Portal")

    If no active/ongoing opportunities are found, return [].

    Content:
    {raw_text[:14000]}
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        clean_json = response.choices.message.content.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"[AI Parse Error] {source_url}: {e}")
        return []

def run_full_global_scan(app, db, Scholarship):
    """Searches the live internet, RSS feeds, and heritage portals, saving new items to the database."""
    print("🌍 Starting live internet + AI global heritage scholarship scan...")
    total_added = 0
    discovered_urls = set(DIRECT_WEB_SOURCES)

    # Step 1: Search the live internet using DuckDuckGo
    try:
        with DDGS() as ddgs:
            for query in LIVE_SEARCH_QUERIES:
                results = ddgs.text(query, max_results=5)
                for r in results:
                    if r.get('href'):
                        discovered_urls.add(r['href'])
                time.sleep(1)
        print(f"🔎 Live web search discovered {len(discovered_urls)} candidate URLs.")
    except Exception as e:
        print(f"[Search Engine Warning]: {e}")

    # Step 2: Gather latest links from RSS & Google News Feeds
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:6]:
                if entry.get('link'):
                    discovered_urls.add(entry['link'])
        except Exception as e:
            print(f"[RSS Warning] {feed_url}: {e}")

    # Step 3: Scrape each page and extract ongoing scholarships with Groq AI
    def save_items(items):
        count = 0
        with app.app_context():
            for idx, item in enumerate(items):
                title = item.get('title', '').strip()
                if not title:
                    continue
                if not Scholarship.query.filter_by(title=title).first():
                    fallback_img = HERITAGE_IMAGES[idx % len(HERITAGE_IMAGES)]
                    record = Scholarship(
                        title=title,
                        organization=item.get('organization', 'Global Heritage Institution'),
                        location=item.get('location', 'International'),
                        image_url=item.get('image_url') or fallback_img,
                        summary=item.get('summary', ''),
                        full_details=item.get('full_details', ''),
                        contact_email=item.get('contact_email', 'See official portal'),
                        contact_phone=item.get('contact_phone', 'Not listed'),
                        apply_url=item.get('apply_url', ''),
                        deadline=item.get('deadline', 'Ongoing')
                    )
                    db.session.add(record)
                    count += 1
            db.session.commit()
        return count

    for url in list(discovered_urls)[:25]:
        raw_text, images = fetch_page_content(url)
        if raw_text:
            items = analyze_with_groq(url, raw_text, images)
            added = save_items(items)
            total_added += added
            if added > 0:
                print(f"✅ Added {added} ongoing scholarship(s) from {url}")
            time.sleep(1.5)

    print(f"🎉 Global AI scan complete! Total new scholarships added to page: {total_added}")
