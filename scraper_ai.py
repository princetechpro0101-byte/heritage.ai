"""
Project: Global Heritage Scholars AI
Project Owner: Dr. Noel Biseko Lwoga
Contact: noelight79@gmail.com | 0784756363
Module: Multi-Source AI Scholarship Gatherer (Groq AI + RSS + Web Scrapers)
"""

import json
import time
import requests
import feedparser
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from groq import Groq

# Requires GROQ_API_KEY in environment variables
client = Groq()

# 1. RSS FEEDS & GOOGLE ALERTS
RSS_AND_ALERT_FEEDS = [
    "https://unesco.org",
    "https://iccrom.org",
    "https://icom.museum",
]

# 2. GLOBAL HERITAGE BODIES & UNIVERSITY ARCHAEOLOGY/HERITAGE DEPARTMENTS
DIRECT_WEB_SOURCES = [
    # Major Global Heritage Organizations
    "https://getty.edu",
    "https://iccrom.org",
    "https://unesco.org",
    "https://icom.museum",
    "https://wmf.org",
    "https://awhf.net",
    "https://britishmuseum.org",
    "https://si.edu",
    "https://wennergren.org",
    
    # University Archaeology & Heritage Departments
    "https://ox.ac.uk",
    "https://cam.ac.uk",
    "https://ucl.ac.uk",
    "https://universiteitleiden.nl",
    "https://udsm.ac.tz"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}

FALLBACK_IMAGE = "https://unsplash.com"

def extract_images(soup, base_url):
    """Extracts valid photo URLs from a webpage so every scholarship card has a picture."""
    urls = []
    for img in soup.find_all('img', src=True):
        src = img['src']
        if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            full_url = urljoin(base_url, src)
            if not any(skip in full_url.lower() for skip in ['logo', 'icon', 'avatar', 'spinner']):
                urls.append(full_url)
    return urls[:8]

def parse_scholarships_with_ai(source_url, raw_text, available_images):
    """Uses Groq (Llama 3.3 70B) to extract scholarship details, contacts, locations, and images."""
    prompt = f"""
    You are a global cultural heritage scholarship researcher for Global Heritage Scholars AI (Owned by Dr. Noel Biseko Lwoga).
    Analyze the text below from: {source_url}

    Extract EVERY active or upcoming scholarship, fellowship, grant, or funded training opportunity in:
    - Cultural Heritage, Conservation & Restoration
    - Archaeology, Anthropology & Paleontology
    - Museum Studies, Curatorial Work & Archival Science
    - World Heritage Site Management

    Return ONLY a valid JSON array of objects with these exact keys:
    - "title": Full official title of the scholarship/fellowship
    - "organization": Host university, museum, or global heritage body
    - "location": Exact City and Country (or "Global / Multiple Locations")
    - "image_url": Select the best matching photo URL from {available_images}. If none fit, use "{FALLBACK_IMAGE}"
    - "summary": 2-sentence overview of who it is for and what it covers
    - "full_details": Complete breakdown of eligibility, funding (tuition, flights, stipend), duration, and application steps
    - "contact_email": Official contact email found in text (or "See official portal")
    - "contact_phone": Official phone number found in text (or "Not listed")
    - "apply_url": Direct application or program URL (use "{source_url}" if no deeper link exists)
    - "deadline": Application closing date (or "Rolling / Check Official Site")

    If no scholarships, grants, or fellowships exist in the text, return [].

    Text to analyze:
    {raw_text[:15000]}
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        clean_json = response.choices[0].message.content.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"[AI Parse Warning] {source_url}: {e}")
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
