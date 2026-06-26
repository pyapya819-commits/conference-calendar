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

# =====================
# 대한고혈압학회 (CV)
# =====================
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

# =====================
# 대한심장학회 (CV)
# =====================
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

# =====================
# 대한신경과학회 (Pain)
# =====================
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

# =====================
# 대한신장학회 (CV)
# =====================
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
                r'\d{2}\.\d{2}(?:\(.+?\))?\s*(?:~\s*\d{2}\.\d{2}(?:\(.+?\))?)?\s*(.+?)(?:\s*-\s*장소|\s*$)', text
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

# =====================
# 대한당뇨병학회 (CV)
# =====================
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

# =====================
# 대한내분비학회 (CV)
# =====================
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

# =====================
# 대한통증학회 (Pain)
# =====================
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

# =====================
# 대한마취통증의학회 (Pain) - 월별 크롤링
# =====================
def crawl_anesthesia():
    print("📡 대한마취통증의학회 크롤링...")
    results = []
    base = 'https://www.anesthesia.or.kr'
    kw = ['마취','통증','pain','학술대회','심포지엄','춘계','추계','포럼']
    for month in range(1, 13):
        url = f'{base}/bbs/index.html?code=schedule&mode=list&year={CURRENT_YEAR}&month={month}'
        soup = get_soup(url)
        if not soup:
            continue
        for a in soup.select('a[href*="schedule"]'):
            text = a.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            if not any(k.lower() in text.lower() for k in kw):
                continue
            # 날짜는 부모 셀에서 추출
            parent = a.find_parent(['td', 'li', 'div'])
            full_text = parent.get_text(separator=' ', strip=True) if parent else text
            date_match = re.search(rf'{month:02d}/(\d{{1,2}})', full_text)
            if not date_match:
                # 테이블 헤더에서 날짜 찾기
                td = a.find_parent('td')
                if td:
                    prev = td.find_previous_sibling('td')
                    if prev:
                        dm = re.search(r'(\d{1,2})', prev.get_text())
                        if dm:
                            d = int(dm.group(1))
                            start = f"{CURRENT_YEAR:04d}-{month:02d}-{d:02d}"
                        else:
                            continue
                    else:
                        continue
                else:
                    continue
            else:
                d = int(date_match.group(1))
                start = f"{CURRENT_YEAR:04d}-{month:02d}-{d:02d}"

            href = a.get('href', '')
            if href and not href.startswith('http'):
                href = base + href

            intl_kw = ['국제','International','ESA','JSA','ASRA','WAPM']
            event_type = 'intl' if any(k.lower() in text.lower() for k in intl_kw) else 'domestic'
            ev = make_event(text, start, start, '장소 미정', 'pain', event_type, '대한마취통증의학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")
        time.sleep(DELAY)
    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 대한신경외과학회 (Pain) - 월별 크롤링
# =====================
def crawl_neurosurgery():
    print("📡 대한신경외과학회 크롤링...")
    results = []
    base = 'https://www.neurosurgery.or.kr'
    for month in range(1, 13):
        url = f'{base}/bbs/index.html?code=schedule&mode=list&year={CURRENT_YEAR}&month={month}'
        soup = get_soup(url)
        if not soup:
            continue
        for a in soup.select('a[href*="schedule"]'):
            text = a.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            if any(k in text for k in ['이사회','상임이사','사무국','위원회']):
                continue
            td = a.find_parent('td')
            if not td:
                continue
            # 해당 날짜 찾기 - 같은 행의 앞 셀
            row = td.find_parent('tr')
            if not row:
                continue
            cells = row.find_all('td')
            date_cell = cells[0] if cells else None
            if not date_cell:
                continue
            dm = re.search(r'(\d{1,2})', date_cell.get_text())
            if not dm:
                continue
            d = int(dm.group(1))
            start = f"{CURRENT_YEAR:04d}-{month:02d}-{d:02d}"
            href = a.get('href', '')
            if href and not href.startswith('http'):
                href = base + href
            intl_kw = ['WFNS','AANS','International','국제','Asia','ASNO']
            event_type = 'intl' if any(k.lower() in text.lower() for k in intl_kw) else 'domestic'
            ev = make_event(text, start, start, '장소 미정', 'pain', event_type, '대한신경외과학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")
        time.sleep(DELAY)
    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 대한재활의학회 (Pain)
# =====================
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

# =====================
# 메디킹 크롤링 (국내 Pain/CV 통합)
# =====================
def crawl_mediking():
    print("📡 메디킹 크롤링...")
    results = []
    soup = get_soup('https://mediking.net/service/conference/16/')
    if not soup:
        return results

    # Viatris 타겟 키워드
    cv_kw = ['고혈압','심장','심혈관','당뇨','내분비','신장','콩팥','TCTAP','지질','동맥경화','심부전','부정맥','내과']
    pain_kw = ['정형외과','신경외과','마취','통증','재활','척추','관절','신경과','두통','뇌졸중']

    text = soup.get_text(separator='\n')
    lines = text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # 날짜 패턴 매칭: "4/16-18" 또는 "4/17" 형식
        date_match = re.match(r'^(\d{1,2})/(\d{1,2})(?:-(\d{1,2}))?$', line)
        if date_match and i + 1 < len(lines):
            mo = int(date_match.group(1))
            d_start = int(date_match.group(2))
            d_end = int(date_match.group(3)) if date_match.group(3) else d_start

            name = lines[i+1].strip() if i+1 < len(lines) else ''
            location = lines[i+2].strip() if i+2 < len(lines) else '장소 미정'

            # 장소가 비어있거나 다음 날짜면 스킵
            if not location or re.match(r'^\d{1,2}/', location):
                location = '장소 미정'

            start = f"{CURRENT_YEAR:04d}-{mo:02d}-{d_start:02d}"
            end = f"{CURRENT_YEAR:04d}-{mo:02d}-{d_end:02d}"

            if name and len(name) > 3:
                # 카테고리 분류
                is_cv = any(k in name for k in cv_kw)
                is_pain = any(k in name for k in pain_kw)

                if is_cv or is_pain:
                    category = 'cv' if is_cv else 'pain'
                    intl_kw = ['국제','TCTAP','International']
                    event_type = 'intl' if any(k in name for k in intl_kw) else 'domestic'
                    ev = make_event(name, start, end, location, category, event_type, '메디킹', 'https://mediking.net/service/conference/16/')
                    if ev:
                        results.append(ev)
                        print(f"  ✅ {name} ({start})")
        i += 1

    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 주요 해외학회 하드코딩 (CV + Pain)
# =====================
def get_intl_conferences():
    print("📡 주요 해외학회 데이터 추가...")
    y = CURRENT_YEAR
    data = [
        # ===== CV 해외학회 =====
        {
            'name': 'ACC 2026 (미국심장학회 연례학술대회)',
            'start': f'{y}-03-28', 'end': f'{y}-03-30',
            'location': '뉴올리언스, 미국',
            'category': 'cv', 'type': 'intl',
            'source': 'ACC', 'url': 'https://accscientificsession.acc.org'
        },
        {
            'name': 'ACC Asia 2026 + KSC Spring (한국심장학회 공동)',
            'start': f'{y}-04-17', 'end': f'{y}-04-18',
            'location': '서울, 한국',
            'category': 'cv', 'type': 'intl',
            'source': 'ACC/KSC', 'url': 'https://www.acc.org'
        },
        {
            'name': 'EHRA 2026 (유럽심장부정맥학회)',
            'start': f'{y}-04-12', 'end': f'{y}-04-14',
            'location': '파리, 프랑스',
            'category': 'cv', 'type': 'intl',
            'source': 'ESC/EHRA', 'url': 'https://www.escardio.org'
        },
        {
            'name': 'ESC Heart Failure 2026',
            'start': f'{y}-05-09', 'end': f'{y}-05-12',
            'location': '바르셀로나, 스페인',
            'category': 'cv', 'type': 'intl',
            'source': 'ESC', 'url': 'https://www.escardio.org'
        },
        {
            'name': 'TCTAP 2026 (관상동맥중재술 아시아태평양)',
            'start': f'{y}-04-29', 'end': f'{y}-05-02',
            'location': '서울, 한국',
            'category': 'cv', 'type': 'intl',
            'source': 'TCTAP', 'url': 'https://www.tctap.org'
        },
        {
            'name': '춘계심혈관통합학술대회',
            'start': f'{y}-04-17', 'end': f'{y}-04-18',
            'location': '서울, 한국',
            'category': 'cv', 'type': 'domestic',
            'source': '심혈관학회', 'url': ''
        },
        {
            'name': 'ESC Congress 2026 (유럽심장학회)',
            'start': f'{y}-08-28', 'end': f'{y}-08-31',
            'location': '뮌헨, 독일',
            'category': 'cv', 'type': 'intl',
            'source': 'ESC', 'url': 'https://www.escardio.org'
        },
        {
            'name': 'TCT 2026 (경피적관상동맥중재술학회)',
            'start': f'{y}-10-31', 'end': f'{y}-11-03',
            'location': '샌디에이고, 미국',
            'category': 'cv', 'type': 'intl',
            'source': 'TCT', 'url': 'https://www.tctconference.com'
        },
        {
            'name': 'AHA Scientific Sessions 2026 (미국심장협회)',
            'start': f'{y}-11-07', 'end': f'{y}-11-09',
            'location': '시카고, 미국',
            'category': 'cv', 'type': 'intl',
            'source': 'AHA', 'url': 'https://www.heart.org'
        },
        # ===== Pain 해외학회 =====
        {
            'name': 'PainConnect 2026 (AAPM 미국통증의학회)',
            'start': f'{y}-03-05', 'end': f'{y}-03-08',
            'location': '솔트레이크시티, 미국',
            'category': 'pain', 'type': 'intl',
            'source': 'AAPM', 'url': 'https://www.painmed.org'
        },
        {
            'name': 'AAN Annual Meeting 2026 (미국신경과학회)',
            'start': f'{y}-04-18', 'end': f'{y}-04-22',
            'location': '시카고, 미국',
            'category': 'pain', 'type': 'intl',
            'source': 'AAN', 'url': 'https://www.aan.com'
        },
        {
            'name': 'AANS Annual Meeting 2026 (미국신경외과학회)',
            'start': f'{y}-05-01', 'end': f'{y}-05-04',
            'location': '샌안토니오, 미국',
            'category': 'pain', 'type': 'intl',
            'source': 'AANS', 'url': 'https://www.aans.org'
        },
        {
            'name': 'AHS Annual Meeting 2026 (미국두통학회)',
            'start': f'{y}-06-04', 'end': f'{y}-06-07',
            'location': '올랜도, 미국',
            'category': 'pain', 'type': 'intl',
            'source': 'AHS', 'url': 'https://americanheadachesociety.org'
        },
        {
            'name': 'EAN Congress 2026 (유럽신경과학회)',
            'start': f'{y}-06-27', 'end': f'{y}-06-30',
            'location': '제네바, 스위스',
            'category': 'pain', 'type': 'intl',
            'source': 'EAN', 'url': 'https://www.ean.org'
        },
        {
            'name': 'IASP World Congress on Pain 2026 (세계통증학회)',
            'start': f'{y}-10-26', 'end': f'{y}-10-30',
            'location': '방콕, 태국',
            'category': 'pain', 'type': 'intl',
            'source': 'IASP', 'url': 'https://www.iasp-pain.org'
        },
        # ===== 정형외과 해외학회 =====
        {
            'name': 'AAOS Annual Meeting 2026 (미국정형외과학회)',
            'start': f'{y}-03-11', 'end': f'{y}-03-15',
            'location': '라스베이거스, 미국',
            'category': 'pain', 'type': 'intl',
            'source': 'AAOS', 'url': 'https://www.aaos.org'
        },
    ]

    results = []
    for item in data:
        ev = make_event(
            item['name'], item['start'], item['end'],
            item['location'], item['category'], item['type'],
            item['source'], item['url']
        )
        if ev:
            results.append(ev)
            print(f"  ✅ {item['name']} ({item['start']})")

    print(f"  → {len(results)}건 추가")
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
        crawl_anesthesia,
        crawl_neurosurgery,
        crawl_rehabilitation,
        crawl_mediking,
        get_intl_conferences,
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
