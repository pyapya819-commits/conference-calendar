#!/usr/bin/env python3
import json
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
}
OUTPUT_PATH = Path(__file__).parent / 'data' / 'conferences.json'
TIMEOUT = 15
DELAY = 1.5
CURRENT_YEAR = datetime.now().year

def get_soup(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        res.encoding = res.apparent_encoding or 'utf-8'
        return BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        print(f"  ⚠️ 접근 실패: {url} → {e}")
        return None

def make_event(name, start, end, location, category, event_type, source, url=''):
    if not start or not name or len(name) < 3:
        return None
    if start < f"{CURRENT_YEAR - 1}-01-01":
        return None
    if not end or end < start:
        end = start
    name = re.sub(r'\s{2,}', ' ', name).strip()
    if not name or len(name) < 3:
        return None
    return {
        'name': name,
        'start': start,
        'end': end,
        'location': location.strip() if location else '장소 미정',
        'category': category,
        'type': event_type,
        'source': source,
        'url': url,
    }

# =====================
# 대한심장학회 (CV) - 테스트
# =====================
def crawl_cardiology():
    print("📡 대한심장학회 크롤링...")
    results = []
    base = 'https://m.circulation.or.kr'
    skip_kw = ['이사회', '상임이사', '총회', '위원회', '간담회', '사무국', '선거']

    for month in range(1, 13):
        url = f'{base}/bbs/index.php?code=meeting&mode=list&year={CURRENT_YEAR}&month={month}&category='
        soup = get_soup(url)
        if not soup:
            continue

        rows = soup.select('table tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            date_text = cells[0].get_text(strip=True)
            name_text = cells[1].get_text(strip=True)

            start_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
            if not start_match:
                continue
            start = start_match.group(1)

            end_match = re.search(r'~\s*(\d{4}-\d{2}-\d{2})', date_text)
            end = end_match.group(1) if end_match else start

            name = re.sub(r'\[국내행사\]|\[국외행사\]|\[연구회\s*행사\]|\[지회행사\]', '', name_text).strip()
            if not name or len(name) < 3:
                continue
            if any(k in name for k in skip_kw):
                continue

            a = cells[1].find('a')
            href = ''
            if a:
                href = a.get('href', '')
                if href and not href.startswith('http'):
                    href = base + href

            intl_kw = ['국외행사', 'International', 'ACC', 'AHA', 'ESC',
                       'JCS', 'TCT', 'TCTAP', 'Asia', 'World']
            event_type = 'intl' if any(k in name_text for k in intl_kw) else 'domestic'

            ev = make_event(name, start, end, '장소 미정', 'cv', event_type, '대한심장학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start}~{end})")

        time.sleep(DELAY)

    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 중복 제거 및 정렬
# =====================
def deduplicate(conferences):
    seen = set()
    result = []
    for c in conferences:
        key = (c['name'][:30], c['start'])
        if key not in seen:
            seen.add(key)
            result.append(c)
    return sorted(result, key=lambda x: x['start'])

# =====================
# 메인
# =====================
def main():
    print("\n" + "="*50)
    print(f"🏥 대한심장학회 크롤링 테스트")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50 + "\n")

    all_conferences = []
    try:
        results = crawl_cardiology()
        all_conferences.extend(results)
    except Exception as e:
        print(f"  ❌ 오류: {e}")
        traceback.print_exc()

    all_conferences = deduplicate(all_conferences)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        'last_updated': datetime.now().strftime('%Y-%m-%d'),
        'total': len(all_conferences),
        'conferences': all_conferences
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료! 총 {len(all_conferences)}건 저장")
    for c in all_conferences:
        print(f"  - {c['start']} {c['name']}")

if __name__ == '__main__':
    main()
