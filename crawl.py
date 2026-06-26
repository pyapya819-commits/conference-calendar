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
    name = re.sub(r'^(국내|국외|국제)\s*\d{1,2}월\s*\d{1,2}일?\(.+?\)\s*', '', name)
    name = re.sub(r'\s*장소\s*[:：].+$', '', name)
    name = re.sub(r'\s*\+\s*자세히\s*보기.*$', '', name)
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

def crawl_hypertension():
    print("📡 대한고혈압학회 크롤링...")
    results = []
    base = 'https://www.koreanhypertension.org'
    for year in [CURRENT_YEAR, CURRENT_YEAR + 1]:
        soup = get_soup(f'{base}/symposium/symposium?year={year}')
        if not soup:
            continue
        for item in soup.select('ul li'):
            a = item.find('a', href=re.compile('symposium.*mode=read'))
            if not a:
                continue
            name = a.get_text(strip=True)
            if not name or len(name) < 5:
                continue
            href = a.get('href', '')
            if not href.startswith('http'):
                href = base + href
            parent_text = item.get_text(separator=' ', strip=True)
            date_match = re.search(r'(\d{2}-\d{2})\s*~\s*(\d{2}-\d{2})', parent_text)
            single_match = re.search(r'(\d{2}-\d{2})', parent_text)
            if date_match:
                start = f"{year}-{date_match.group(1)}"
                end = f"{year}-{date_match.group(2)}"
            elif single_match:
                start = f"{year}-{single_match.group(1)}"
                end = start
            else:
                continue
            intl_kw = ['ESH','JSH','ISH','AHA','ACC','ESC','International','European','American']
            event_type = 'intl' if any(k.lower() in name.lower() for k in intl_kw) else 'domestic'
            location = '장소 미정'
            time.sleep(DELAY)
            detail = get_soup(href)
            if detail:
                for row in detail.select('table tr'):
                    cells = row.find_all(['th', 'td'])
                    for i, cell in enumerate(cells):
                        if '장소' in cell.get_text():
                            if i + 1 < len(cells):
                                location = cells[i+1].get_text(strip=True)
                            break
            ev = make_event(name, start, end, location, 'cv', event_type, '대한고혈압학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {name} ({start})")
        time.sleep(DELAY)
    print(f"  → {len(results)}건 수집")
    return results

def crawl_cardiology():
    print("📡 대한심장학회 크롤링...")
    results = []
    base = 'https://circulation.or.kr'
    for page in range(1, 6):
        soup = get_soup(f'{base}/workshop/sub1.php?page={page}')
        if not soup:
            break
        found = False
        for row in soup.select('table tr'):
            text = row.get_text(separator=' ', strip=True)
            if not text or len(text) < 10:
                continue
            date_match = re.search(r'(\d{4})[년.\-]?\s*(\d{1,2})[월.\-]?\s*(\d{1,2})', text)
            if not date_match:
                continue
            y, mo, d = date_match.groups()
            if int(y) < CURRENT_YEAR:
                continue
            found = True
            start = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            a = row.find('a')
            name = a.get_text(strip=True) if a else text[:60]
            if not name or len(name) < 5:
                continue
            href = ''
            if a:
                href = a.get('href', '')
                if href and not href.startswith('http'):
                    href = base + '/' + href.lstrip('/')
            intl_kw = ['국제','International','ACC','AHA','ESC','Asia']
            event_type = 'intl' if any(k.lower() in name.lower() for k in intl_kw) else 'domestic'
            ev = make_event(name, start, start, '장소 미정', 'cv', event_type, '대한심장학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {name} ({start})")
        if not found:
            break
        time.sleep(DELAY)
    print(f"  → {len(results)}건 수집")
    return results

def crawl_neurology():
    print("📡 대한신경과학회 크롤링...")
    results = []
    base = 'https://renew.neuro.or.kr'
    for page in range(1, 8):
        soup = get_soup(f'{base}/kr/board_list/do-schedule?year={CURRENT_YEAR}&page={page}')
        if not soup:
            break
        items = soup.select('li')
        found = False
        for item in items:
            text = item.get_text(separator=' ', strip=True)
            if not text or len(text) < 10:
                continue
            if '장소' not in text and '자세히' not in text:
                continue
            date_match = re.search(r'(\d{1,2})월\s*(\d{1,2})', text)
            if not date_match:
                continue
            found = True
            mo, d = date_match.groups()
            start = f"{CURRENT_YEAR:04d}-{int(mo):02d}-{int(d):02d}"
            end = start
            end_match = re.search(r'~\s*(\d{1,2})\(', text)
            if end_match:
                end = f"{CURRENT_YEAR:04d}-{int(mo):02d}-{int(end_match.group(1)):02d}"
            name_match = re.search(
                r'\d+월\s*\d+\(.+?\)\s*(?:~\s*\d+\(.+?\)\s*)?(.+?)(?:장소|자세히|$)', text
            )
            name = name_match.group(1).strip() if name_match else text[:80]
            loc_match = re.search(r'장소\s*[:：]\s*(.+?)(?:\s*\+|\s*$)', text)
            location = loc_match.group(1).strip() if loc_match else '장소 미정'
            a = item.find('a', href=re.compile('do-schedule/view'))
            href = ''
            if a:
                href = a.get('href', '')
                if not href.startswith('http'):
                    href = base + href
            intl_kw = ['국제','International','WFN','AAN','EAN','WSC','EFNS']
            event_type = 'intl' if any(k.lower() in name.lower() for k in intl_kw) else 'domestic'
            ev = make_event(name, start, end, location, 'pain', event_type, '대한신경과학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")
        if not found:
            break
        time.sleep(DELAY)
    print(f"  → {len(results)}건 수집")
    return results

def crawl_nephrology():
    print("📡 대한신장학회 크롤링...")
    results = []
    base = 'https://www.ksn.or.kr'
    kidney_kw = ['신장', '투석', '이식', '콩팥', 'KSN', 'ERA', 'ISN', 'ASN', 'JSDT', 'CRRT', 'AKI', 'CKD', '혈액투석', '복막투석']
    for month in range(1, 13):
        url = f'{base}/bbs/index.php?code=schedule&year={CURRENT_YEAR}&month={month}'
        soup = get_soup(url)
        if not soup:
            continue
        for item in soup.select('li'):
            text = item.get_text(separator=' ', strip=True)
            if not text or len(text) < 10:
                continue
            date_match = re.search(r'(\d{2})\.(\d{2})', text)
            if not date_match:
                continue
            mo, d = date_match.groups()
            start = f"{CURRENT_YEAR:04d}-{int(mo):02d}-{int(d):02d}"
            end_match = re.search(r'~\s*(\d{2})\.(\d{2})', text)
            end = start
            if end_match:
                emo, ed = end_match.groups()
                end = f"{CURRENT_YEAR:04d}-{int(emo):02d}-{int(ed):02d}"
            name_match = re.search(
                r'\d{2}\.\d{2}(?:\(.+?\))?\s*(?:~\s*\d{2}\.\d{2}(?:\(.+?\))?)?\s*(.+?)(?:\s*-\s*장소|\s*$)',
                text
            )
            name = name_match.group(1).strip() if name_match else text[:80]
            if not name or len(name) < 5:
                continue
            if not any(k.lower() in name.lower() or k.lower() in text.lower() for k in kidney_kw):
                continue
            loc_match = re.search(r'장소\s*[:：]?\s*(.+?)(?:\s*$)', text)
            location = loc_match.group(1).strip() if loc_match else '장소 미정'
            intl_kw = ['ISN','ERA','ASN','International','국제','JSN','JSDT','WCN','ESPN','ISPD','CRRT']
            event_type = 'intl' if any(k.lower() in name.lower() for k in intl_kw) else 'domestic'
            ev = make_event(name, start, end, location, 'cv', event_type, '대한신장학회', '')
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")
        time.sleep(DELAY)
    print(f"  → {len(results)}건 수집")
    return results

def crawl_diabetes():
    print("📡 대한당뇨병학회 크롤링...")
    results = []
    base = 'https://www.diabetes.or.kr'
    for page in range(1, 6):
        url = f'{base}/bbs/?code=schedule&page={page}'
        soup = get_soup(url)
        if not soup:
            break
        found = False
        for row in soup.select('table tr'):
            text = row.get_text(separator=' ', strip=True)
            if not text or len(text) < 10:
                continue
            date_match = re.search(r'(\d{4})[.\-년\s](\d{1,2})[.\-월\s](\d{1,2})', text)
            if not date_match:
                continue
            y, mo, d = date_match.groups()
            if int(y) < CURRENT_YEAR:
                continue
            found = True
            start = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            end_match = re.search(r'~\s*(\d{4})?[.\-년\s]?(\d{1,2})[.\-월\s](\d{1,2})', text)
            end = start
            if end_match:
                ey = end_match.group(1) or y
                end = f"{int(ey):04d}-{int(end_match.group(2)):02d}-{int(end_match.group(3)):02d}"
            a = row.find('a')
            name = a.get_text(strip=True) if a else text[:60]
            if not name or len(name) < 5:
                continue
            href = ''
            if a:
                href = a.get('href', '')
                if href and not href.startswith('http'):
                    href = base + href
            loc_match = re.search(r'([\w\s]+(?:센터|호텔|홀|대학교|컨벤션|COEX|BEXCO)[\w\s]*)', text)
            location = loc_match.group(1).strip() if loc_match else '장소 미정'
            intl_kw = ['ADA','EASD','IDF','International','국제','ICDM','AASD']
            event_type = 'intl' if any(k.lower() in name.lower() for k in intl_kw) else 'domestic'
            ev = make_event(name, start, end, location, 'cv', event_type, '대한당뇨병학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")
        if not found:
            break
        time.sleep(DELAY)
    print(f"  → {len(results)}건 수집")
    return results

def crawl_orthopedics():
    print("📡 대한정형외과학회 크롤링...")
    results = []
    base = 'https://www.koa.or.kr'
    for code, label in [('event1', 'domestic'), ('event2', 'intl')]:
        for page in range(1, 5):
            soup = get_soup(f'{base}/bbs/?code={code}&page={page}')
            if not soup:
                break
            found = False
            for row in soup.select('table tr'):
                text = row.get_text(separator=' ', strip=True)
                date_match = re.search(r'(\d{4})[.\-년](\d{1,2})[.\-월](\d{1,2})', text)
                if not date_match:
                    continue
                y, mo, d = date_match.groups()
                if int(y) < CURRENT_YEAR:
                    continue
                found = True
                start = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
                a = row.find('a')
                name = a.get_text(strip=True) if a else text[:60]
                if not name or len(name) < 5:
                    continue
                href = ''
                if a:
                    href = a.get('href', '')
                    if href and not href.startswith('http'):
                        href = base + href
                ev = make_event(name, start, start, '장소 미정', 'pain', label, '대한정형외과학회', href)
                if ev:
                    results.append(ev)
                    print(f"  ✅ {ev['name']} ({start})")
            if not found:
                break
            time.sleep(DELAY)
    print(f"  → {len(results)}건 수집")
    return results

def crawl_anesthesia():
    print("📡 대한마취통증의학회 크롤링...")
    results = []
    soup = get_soup('https://www.anesthesia.or.kr/index.php')
    if not soup:
        return results
    seen = set()
    for item in soup.select('a, li'):
        text = item.get_text(strip=True)
        if not text or len(text) < 10 or text in seen:
            continue
        if not any(k in text for k in ['학술대회','심포지엄','춘계','추계','Annual']):
            continue
        seen.add(text)
        date_match = re.search(r'(\d{4})[.\-년](\d{1,2})[.\-월](\d{1,2})', text)
        if not date_match:
            continue
        y, mo, d = date_match.groups()
        if int(y) < CURRENT_YEAR:
            continue
        start = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        name = text[:80].strip()
        href = item.get('href', '') if item.name == 'a' else ''
        ev = make_event(name, start, start, '장소 미정', 'pain', 'domestic', '대한마취통증의학회', href)
        if ev:
            results.append(ev)
            print(f"  ✅ {ev['name']} ({start})")
    print(f"  → {len(results)}건 수집")
    return results

def crawl_rehabilitation():
    print("📡 대한재활의학회 크롤링...")
    results = []
    for page in range(1, 4):
        soup = get_soup(f'https://www.karm.or.kr/bbs/?code=schedule&page={page}')
        if not soup:
            break
        seen = set()
        found = False
        for item in soup.select('table tr, li, a'):
            text = item.get_text(strip=True)
            if not text or len(text) < 10 or text in seen:
                continue
            if not any(k in text for k in ['학술','심포지엄','춘계','추계']):
                continue
            seen.add(text)
            date_match = re.search(r'(\d{4})[.\-년](\d{1,2})[.\-월](\d{1,2})', text)
            if not date_match:
                continue
            y, mo, d = date_match.groups()
            if int(y) < CURRENT_YEAR:
                continue
            found = True
            start = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            name = text[:80].strip()
            href = item.get('href', '') if item.name == 'a' else ''
            ev = make_event(name, start, start, '장소 미정', 'pain', 'domestic', '대한재활의학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")
        if not found:
            break
        time.sleep(DELAY)
    print(f"  → {len(results)}건 수집")
    return results

def crawl_neurosurgery():
    print("📡 대한신경외과학회 크롤링...")
    results = []
    soup = get_soup('https://www.neurosurgery.or.kr/conference/')
    if not soup:
        return results
    seen = set()
    for item in soup.select('table tr, li'):
        text = item.get_text(strip=True)
        if not text or len(text) < 10 or text in seen:
            continue
        seen.add(text)
        date_match = re.search(r'(\d{4})[.\-년](\d{1,2})[.\-월](\d{1,2})', text)
        if not date_match:
            continue
        y, mo, d = date_match.groups()
        if int(y) < CURRENT_YEAR:
            continue
        start = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        a = item.find('a') if hasattr(item, 'find') else None
        name = a.get_text(strip=True) if a else text[:60]
        if not name or len(name) < 5:
            continue
        loc_match = re.search(r'([\w\s]+(?:센터|호텔|홀|컨벤션)[\w\s]*)', text)
        location = loc_match.group(1).strip() if loc_match else '장소 미정'
        intl_kw = ['WFNS','AANS','International','국제']
        event_type = 'intl' if any(k.lower() in name.lower() for k in intl_kw) else 'domestic'
        href = item.get('href', '') if item.name == 'a' else ''
        ev = make_event(name, start, start, location, 'pain', event_type, '대한신경외과학회', href)
        if ev:
            results.append(ev)
            print(f"  ✅ {ev['name']} ({start})")
    print(f"  → {len(results)}건 수집")
    return results

def crawl_pain():
    print("📡 대한통증학회 크롤링...")
    results = []
    soup = get_soup('https://www.painfree.or.kr/main.html')
    if not soup:
        return results
    seen = set()
    for item in soup.select('a, li'):
        text = item.get_text(strip=True)
        if not text or len(text) < 10 or text in seen:
            continue
        if not any(k in text for k in ['학술대회','심포지엄','춘계','추계']):
            continue
        seen.add(text)
        date_match = re.search(r'(\d{4})[.\-년](\d{1,2})[.\-월](\d{1,2})', text)
        if not date_match:
            continue
        y, mo, d = date_match.groups()
        if int(y) < CURRENT_YEAR:
            continue
        start = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        name = text[:80].strip()
        href = item.get('href', '') if item.name == 'a' else ''
        if href and not href.startswith('http'):
            href = 'https://www.painfree.or.kr' + href
        ev = make_event(name, start, start, '장소 미정', 'pain', 'domestic', '대한통증학회', href)
        if ev:
            results.append(ev)
            print(f"  ✅ {ev['name']} ({start})")
    print(f"  → {len(results)}건 수집")
    return results

def crawl_endocrinology():
    print("📡 대한내분비학회 크롤링...")
    results = []
    for page in range(1, 4):
        soup = get_soup(f'https://endocrinology.or.kr/event/schedule/?page={page}')
        if not soup:
            break
        seen = set()
        found = False
        for item in soup.select('a, li, table tr'):
            text = item.get_text(strip=True)
            if not text or len(text) < 10 or text in seen:
                continue
            if not any(k in text for k in ['학술','심포지엄','SICEM','EASD','ENDO']):
                continue
            seen.add(text)
            date_match = re.search(r'(\d{4})[.\-년](\d{1,2})[.\-월](\d{1,2})', text)
            if not date_match:
                continue
            y, mo, d = date_match.groups()
            if int(y) < CURRENT_YEAR:
                continue
            found = True
            start = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            name = text[:80].strip()
            intl_kw = ['EASD','ENDO','International','국제','SICEM']
            event_type = 'intl' if any(k.lower() in name.lower() for k in intl_kw) else 'domestic'
            href = item.get('href', '') if item.name == 'a' else ''
            ev = make_event(name, start, start, '장소 미정', 'cv', event_type, '대한내분비학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")
        if not found:
            break
        time.sleep(DELAY)
    print(f"  → {len(results)}건 수집")
    return results

def crawl_digital_clinical():
    print("📡 대한디지털임상의학회 크롤링...")
    results = []
    soup = get_soup('https://www.kdcm.or.kr/')
    if not soup:
        return results
    seen = set()
    for item in soup.select('a, li'):
        text = item.get_text(strip=True)
        if not text or len(text) < 10 or text in seen:
            continue
        if not any(k in text for k in ['학술','심포지엄','대회','컨퍼런스']):
            continue
        seen.add(text)
        date_match = re.search(r'(\d{4})[.\-년](\d{1,2})[.\-월](\d{1,2})', text)
        if not date_match:
            continue
        y, mo, d = date_match.groups()
        if int(y) < CURRENT_YEAR:
            continue
        start = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        name = text[:80].strip()
        href = item.get('href', '') if item.name == 'a' else ''
        ev = make_event(name, start, start, '장소 미정', 'cv', 'domestic', '대한디지털임상의학회', href)
        if ev:
            results.append(ev)
            print(f"  ✅ {ev['name']} ({start})")
    print(f"  → {len(results)}건 수집")
    return results

def deduplicate(conferences):
    seen = set()
    result = []
    for c in conferences:
        key = (c['name'][:30], c['start'])
        if key not in seen:
            seen.add(key)
            result.append(c)
    return sorted(result, key=lambda x: x['start'])

def main():
    print("\n" + "="*50)
    print(f"🏥 Viatris 학회 일정 크롤링 시작")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50 + "\n")

    crawlers = [
        crawl_hypertension,
        crawl_cardiology,
        crawl_neurology,
        crawl_pain,
        crawl_diabetes,
        crawl_endocrinology,
        crawl_nephrology,
        crawl_orthopedics,
        crawl_anesthesia,
        crawl_rehabilitation,
        crawl_neurosurgery,
        crawl_digital_clinical,
    ]

    all_conferences = []
    for crawler in crawlers:
        try:
            results = crawler()
            all_conferences.extend(results)
            time.sleep(DELAY)
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

if __name__ == '__main__':
    main()
