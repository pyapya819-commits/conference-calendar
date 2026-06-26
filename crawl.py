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
# 1. 대한고혈압학회 (CV) - 공식 사이트
# =====================
def crawl_hypertension():
    print("📡 대한고혈압학회 크롤링...")
    results = []
    base = 'https://www.koreanhypertension.org'

    for year in [CURRENT_YEAR, CURRENT_YEAR + 1]:
        soup = get_soup(f'{base}/symposium/symposium?year={year}')
        if not soup:
            continue

        for item in soup.select('ul > li, .schedule_list > li, div.list_item'):
            text = item.get_text(separator=' ', strip=True)
            if not text or len(text) < 5:
                continue

            date_match = re.search(r'(\d{2}-\d{2})\s*(?:~\s*(\d{2}-\d{2}))?', text)
            if not date_match:
                continue

            start = f"{year}-{date_match.group(1)}"
            end = f"{year}-{date_match.group(2)}" if date_match.group(2) else start

            a = item.find('a')
            if a:
                name = a.get_text(strip=True)
                href = a.get('href', '')
                if href and not href.startswith('http'):
                    href = base + href
            else:
                name = re.sub(r'\d{2}-\d{2}\s*(?:~\s*\d{2}-\d{2})?\s*', '', text).strip()
                href = ''

            if not name or len(name) < 3:
                continue

            intl_kw = ['ESH', 'ISH', 'JSH', 'AHA', 'ACC', 'ESC', 'International', 'European']
            event_type = 'intl' if any(k.lower() in name.lower() for k in intl_kw) else 'domestic'

            ev = make_event(name, start, end, '장소 미정', 'cv', event_type, '대한고혈압학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")

        time.sleep(DELAY)

    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 2. 대한심장학회 (CV) - 모바일 사이트 월별
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

        for row in soup.select('table tr'):
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            date_text = cells[0].get_text(strip=True)
            name_text = cells[1].get_text(strip=True)

            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
            if not date_match:
                continue

            start = date_match.group(1)
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

            intl_kw = ['국외', 'International', 'ACC', 'AHA', 'ESC', 'JCS', 'TCT', 'TCTAP', 'Asia', 'World']
            event_type = 'intl' if any(k in name_text for k in intl_kw) else 'domestic'

            ev = make_event(name, start, end, '장소 미정', 'cv', event_type, '대한심장학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")

        time.sleep(DELAY)

    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 3. 대한신경과학회 (Pain) - 월별
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

            intl_kw = ['국제', 'International', 'WFN', 'AAN', 'EAN', 'WSC', 'EFNS']
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
# 4. 대한당뇨병학회 (CV)
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

            intl_kw = ['ADA', 'EASD', 'IDF', 'International', '국제', 'ICDM', 'AASD']
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
# 5. 대한신장학회 (CV) - 신장 관련만
# =====================
def crawl_nephrology():
    print("📡 대한신장학회 크롤링...")
    results = []
    base = 'https://www.ksn.or.kr'
    kidney_kw = ['신장', '투석', '이식', '콩팥', 'KSN', 'ERA', 'ISN', 'ASN',
                 'JSDT', 'CRRT', 'AKI', 'CKD', '혈액투석', '복막투석']

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

            intl_kw = ['ISN', 'ERA', 'ASN', 'International', '국제', 'JSDT', 'WCN', 'ISPD', 'CRRT']
            event_type = 'intl' if any(k.lower() in name.lower() for k in intl_kw) else 'domestic'

            ev = make_event(name, start, end, location, 'cv', event_type, '대한신장학회', '')
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")

        time.sleep(DELAY)

    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 6. 대한내분비학회 (CV)
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
            if not any(k in text for k in ['학술', '심포지엄', 'SICEM', 'EASD', 'ENDO']):
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
            intl_kw = ['EASD', 'ENDO', 'International', '국제', 'SICEM']
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
# 7. 대한마취통증의학회 (Pain) - 월별
# =====================
def crawl_anesthesia():
    print("📡 대한마취통증의학회 크롤링...")
    results = []
    base = 'https://www.anesthesia.or.kr'
    kw = ['마취', '통증', 'pain', '학술대회', '심포지엄', '춘계', '추계', '포럼', '연수']

    for month in range(1, 13):
        url = f'{base}/bbs/index.html?code=schedule&mode=list&year={CURRENT_YEAR}&month={month}'
        soup = get_soup(url)
        if not soup:
            continue

        # 캘린더 테이블에서 링크 추출
        for a in soup.select('a[href*="schedule"]'):
            text = a.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            if not any(k.lower() in text.lower() for k in kw):
                continue

            # 날짜는 부모 td에서 추출
            td = a.find_parent('td')
            if not td:
                continue
            row = td.find_parent('tr')
            if not row:
                continue

            # 같은 행의 날짜 셀 찾기
            all_tds = row.find_all('td')
            day = None
            for cell in all_tds:
                dm = re.search(r'^(\d{1,2})$', cell.get_text(strip=True))
                if dm:
                    day = int(dm.group(1))
                    break

            if not day:
                # 링크 텍스트에서 날짜 추출 시도
                dm2 = re.search(rf'{month:02d}/(\d{{1,2}})', text)
                if dm2:
                    day = int(dm2.group(1))
                else:
                    continue

            start = f"{CURRENT_YEAR:04d}-{month:02d}-{day:02d}"
            href = a.get('href', '')
            if href and not href.startswith('http'):
                href = base + href

            intl_kw = ['국제', 'International', 'ESA', 'JSA', 'ASRA', 'WAPM']
            event_type = 'intl' if any(k.lower() in text.lower() for k in intl_kw) else 'domestic'

            ev = make_event(text, start, start, '장소 미정', 'pain', event_type, '대한마취통증의학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")

        time.sleep(DELAY)

    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 8. 대한신경외과학회 (Pain) - 월별
# =====================
def crawl_neurosurgery():
    print("📡 대한신경외과학회 크롤링...")
    results = []
    base = 'https://www.neurosurgery.or.kr'
    skip_kw = ['이사회', '상임이사', '총회', '위원회', '간담회', '사무국']

    for month in range(1, 13):
        url = f'{base}/bbs/index.html?code=schedule&mode=list&year={CURRENT_YEAR}&month={month}'
        soup = get_soup(url)
        if not soup:
            continue

        for a in soup.select('a[href*="schedule"]'):
            text = a.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            if any(k in text for k in skip_kw):
                continue

            td = a.find_parent('td')
            if not td:
                continue
            row = td.find_parent('tr')
            if not row:
                continue

            all_tds = row.find_all('td')
            day = None
            for cell in all_tds:
                dm = re.search(r'^(\d{1,2})$', cell.get_text(strip=True))
                if dm:
                    day = int(dm.group(1))
                    break

            if not day:
                continue

            start = f"{CURRENT_YEAR:04d}-{month:02d}-{day:02d}"
            href = a.get('href', '')
            if href and not href.startswith('http'):
                href = base + href

            intl_kw = ['WFNS', 'AANS', 'International', '국제', 'Asia', 'ASNO']
            event_type = 'intl' if any(k.lower() in text.lower() for k in intl_kw) else 'domestic'

            ev = make_event(text, start, start, '장소 미정', 'pain', event_type, '대한신경외과학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")

        time.sleep(DELAY)

    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 9. 대한통증학회 (Pain)
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
        if not any(k in text for k in ['학술대회', '심포지엄', '춘계', '추계', '연수']):
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
# 10. 대한재활의학회 (Pain)
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
            if not any(k in text for k in ['학술', '심포지엄', '춘계', '추계']):
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
            href = item.get('href', '') if item.name == 'a' else ''
            ev = make_event(text[:80], start, start, '장소 미정', 'pain', 'domestic', '대한재활의학회', href)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({start})")

        if not found:
            break
        time.sleep(DELAY)

    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 11. 메디칼허브 월별 학술대회 (CV + Pain 통합)
#     → 상반기 국내 학회 메인 소스
# =====================
def crawl_healthmedia():
    print("📡 메디칼허브 크롤링...")
    results = []

    cv_kw = ['고혈압', '심장', '심혈관', '당뇨', '내분비', '신장', '지질', '동맥경화',
             '심부전', '내과', 'TCTAP', '대사', '비만', '갑상선', '골다공증', '골대사',
             'SICEM', '부정맥', '심근경색', '뇌혈관', '심뇌혈관', '혈압']
    pain_kw = ['정형외과', '신경외과', '마취', '통증', '재활', '척추', '관절',
               '신경과', '두통', '뇌졸중', '신경', '근골격', '류마티스']
    exclude_kw = ['피부', '안과', '이비인후', '산부인과', '소아', '치과', '한의',
                  '정신', '흉부외과', '비뇨', '성형', '방사선', '병리', '소화기',
                  '종양', '혈액', '폐암', '위암', '간학', '감염']

    # 메디칼허브 학술일정 섹션 검색
    search_url = 'http://www.healthmedia.co.kr/news/articleList.html?sc_sub_section_code=S2N30&view_type=sm'
    soup = get_soup(search_url)
    article_urls = []

    if soup:
        for a in soup.select('a[href*="articleView"]'):
            href = a.get('href', '')
            title = a.get_text(strip=True)
            if str(CURRENT_YEAR) in title and ('학술일정' in title or '국내' in title):
                if not href.startswith('http'):
                    href = 'http://www.healthmedia.co.kr' + href
                if href not in article_urls:
                    article_urls.append(href)

    # 알려진 URL 보완 (검색 실패 시 fallback)
    known_urls = [
        f'http://www.healthmedia.co.kr/news/articleView.html?idxno=104741',  # 3월
        f'http://www.healthmedia.co.kr/news/articleView.html?idxno=104995',  # 4월
        f'http://www.healthmedia.co.kr/news/articleView.html?idxno=105605',  # 6월
    ]
    for u in known_urls:
        if u not in article_urls:
            article_urls.append(u)

    seen = set()
    for url in article_urls:
        time.sleep(DELAY)
        detail = get_soup(url)
        if not detail:
            continue

        content = detail.get_text(separator='\n', strip=True)
        lines = content.split('\n')

        for line in lines:
            line = line.strip()
            date_match = re.match(rf'({CURRENT_YEAR}-\d{{2}}-\d{{2}})\s+(.+)', line)
            if not date_match:
                continue

            date_str = date_match.group(1)
            rest = date_match.group(2).strip()

            if any(ex in rest for ex in exclude_kw):
                continue

            is_cv = any(k in rest for k in cv_kw)
            is_pain = any(k in rest for k in pain_kw)
            if not is_cv and not is_pain:
                continue

            parts = re.split(r'\s{2,}', rest)
            name = parts[0].strip() if parts else rest[:80]
            location = parts[-1].strip() if len(parts) >= 3 else (parts[1].strip() if len(parts) == 2 else '장소 미정')

            if not name or len(name) < 3:
                continue

            key = (name[:20], date_str)
            if key in seen:
                continue
            seen.add(key)

            category = 'cv' if is_cv else 'pain'
            intl_kw_list = ['국제', 'International', 'TCTAP', 'World', 'SICEM', 'Asia']
            event_type = 'intl' if any(k in name for k in intl_kw_list) else 'domestic'

            ev = make_event(name, date_str, date_str, location, category, event_type, '메디칼허브', url)
            if ev:
                results.append(ev)
                print(f"  ✅ {ev['name']} ({date_str})")

    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 12. 메디킹 (국내 Pain/CV 보조)
# =====================
def crawl_mediking():
    print("📡 메디킹 크롤링...")
    results = []
    soup = get_soup('https://mediking.net/service/conference/16/')
    if not soup:
        return results

    cv_kw = ['고혈압', '심장', '심혈관', '당뇨', '내분비', '신장', '지질', '동맥경화', '심부전', '내과', 'TCTAP', '혈압']
    pain_kw = ['정형외과', '신경외과', '마취', '통증', '재활', '척추', '관절', '신경과', '두통']

    text = soup.get_text(separator='\n')
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]
        # "4/16-18" 또는 "4/17" 또는 "4/29-5/2" 형식
        date_match = re.match(r'^(\d{1,2})/(\d{1,2})(?:-(?:(\d{1,2})/)?(\d{1,2}))?$', line)
        if date_match and i + 1 < len(lines):
            mo_s = int(date_match.group(1))
            d_s = int(date_match.group(2))
            mo_e = int(date_match.group(3)) if date_match.group(3) else mo_s
            d_e = int(date_match.group(4)) if date_match.group(4) else d_s

            name = lines[i+1] if i+1 < len(lines) else ''
            location = lines[i+2] if i+2 < len(lines) else '장소 미정'
            if re.match(r'^\d{1,2}/', location):
                location = '장소 미정'

            start = f"{CURRENT_YEAR:04d}-{mo_s:02d}-{d_s:02d}"
            end = f"{CURRENT_YEAR:04d}-{mo_e:02d}-{d_e:02d}"

            is_cv = any(k in name for k in cv_kw)
            is_pain = any(k in name for k in pain_kw)

            if name and len(name) > 3 and (is_cv or is_pain):
                category = 'cv' if is_cv else 'pain'
                intl_kw = ['국제', 'TCTAP', 'International']
                event_type = 'intl' if any(k in name for k in intl_kw) else 'domestic'
                ev = make_event(name, start, end, location, category, event_type, '메디킹',
                                'https://mediking.net/service/conference/16/')
                if ev:
                    results.append(ev)
                    print(f"  ✅ {name} ({start})")
        i += 1

    print(f"  → {len(results)}건 수집")
    return results

# =====================
# 13. 주요 해외학회 하드코딩 (CV + Pain)
#     → 매년 고정 업데이트 필요
# =====================
def get_intl_conferences():
    print("📡 주요 해외학회 데이터 추가...")
    y = CURRENT_YEAR
    data = [
        # ===== CV 해외 =====
        {'name': 'ACC 2026 (미국심장학회)', 'start': f'{y}-03-28', 'end': f'{y}-03-30',
         'location': '뉴올리언스, 미국', 'category': 'cv', 'type': 'intl',
         'source': 'ACC', 'url': 'https://accscientificsession.acc.org'},
        {'name': 'ACC Asia 2026 + KSC 춘계 (한국 개최)',  'start': f'{y}-04-17', 'end': f'{y}-04-18',
         'location': '경주, 한국', 'category': 'cv', 'type': 'intl',
         'source': 'ACC/KSC', 'url': 'https://www.acc.org'},
        {'name': 'EHRA 2026 (유럽심장부정맥학회)', 'start': f'{y}-04-12', 'end': f'{y}-04-14',
         'location': '파리, 프랑스', 'category': 'cv', 'type': 'intl',
         'source': 'ESC/EHRA', 'url': 'https://www.escardio.org'},
        {'name': 'ESC Heart Failure 2026', 'start': f'{y}-05-09', 'end': f'{y}-05-12',
         'location': '바르셀로나, 스페인', 'category': 'cv', 'type': 'intl',
         'source': 'ESC', 'url': 'https://www.escardio.org'},
        {'name': 'TCTAP 2026 (관상동맥중재술 아시아태평양)', 'start': f'{y}-04-29', 'end': f'{y}-05-02',
         'location': '서울, 한국', 'category': 'cv', 'type': 'intl',
         'source': 'TCTAP', 'url': 'https://www.tctap.org'},
        {'name': 'ESH 2026 (유럽고혈압학회)', 'start': f'{y}-05-28', 'end': f'{y}-05-31',
         'location': '유럽', 'category': 'cv', 'type': 'intl',
         'source': 'ESH', 'url': 'https://eshannualmeetings.eu'},
        {'name': 'ESC Congress 2026 (유럽심장학회)', 'start': f'{y}-08-28', 'end': f'{y}-08-31',
         'location': '뮌헨, 독일', 'category': 'cv', 'type': 'intl',
         'source': 'ESC', 'url': 'https://www.escardio.org'},
        {'name': 'JSH 2026 (일본고혈압학회)', 'start': f'{y}-10-10', 'end': f'{y}-10-12',
         'location': '일본', 'category': 'cv', 'type': 'intl',
         'source': 'JSH', 'url': 'https://www.congre.co.jp/48jsh2026'},
        {'name': 'ISH 2026 (국제고혈압학회)', 'start': f'{y}-10-22', 'end': f'{y}-10-25',
         'location': 'UAE', 'category': 'cv', 'type': 'intl',
         'source': 'ISH', 'url': 'https://ishecs26.org'},
        {'name': 'TCT 2026 (경피적관상동맥중재술학회)', 'start': f'{y}-10-31', 'end': f'{y}-11-03',
         'location': '샌디에이고, 미국', 'category': 'cv', 'type': 'intl',
         'source': 'TCT', 'url': 'https://www.tctconference.com'},
        {'name': 'AHA Scientific Sessions 2026 (미국심장협회)', 'start': f'{y}-11-07', 'end': f'{y}-11-09',
         'location': '시카고, 미국', 'category': 'cv', 'type': 'intl',
         'source': 'AHA', 'url': 'https://www.heart.org'},
        # ===== Pain 해외 =====
        {'name': 'PainConnect 2026 (AAPM 미국통증의학회)', 'start': f'{y}-03-05', 'end': f'{y}-03-08',
         'location': '솔트레이크시티, 미국', 'category': 'pain', 'type': 'intl',
         'source': 'AAPM', 'url': 'https://www.painmed.org'},
        {'name': 'AAOS Annual Meeting 2026 (미국정형외과학회)', 'start': f'{y}-03-11', 'end': f'{y}-03-15',
         'location': '라스베이거스, 미국', 'category': 'pain', 'type': 'intl',
         'source': 'AAOS', 'url': 'https://www.aaos.org'},
        {'name': 'AAN Annual Meeting 2026 (미국신경과학회)', 'start': f'{y}-04-18', 'end': f'{y}-04-22',
         'location': '시카고, 미국', 'category': 'pain', 'type': 'intl',
         'source': 'AAN', 'url': 'https://www.aan.com'},
        {'name': 'AANS Annual Meeting 2026 (미국신경외과학회)', 'start': f'{y}-05-01', 'end': f'{y}-05-04',
         'location': '샌안토니오, 미국', 'category': 'pain', 'type': 'intl',
         'source': 'AANS', 'url': 'https://www.aans.org'},
        {'name': 'AHS Annual Meeting 2026 (미국두통학회)', 'start': f'{y}-06-04', 'end': f'{y}-06-07',
         'location': '올랜도, 미국', 'category': 'pain', 'type': 'intl',
         'source': 'AHS', 'url': 'https://americanheadachesociety.org'},
        {'name': 'EAN Congress 2026 (유럽신경과학회)', 'start': f'{y}-06-27', 'end': f'{y}-06-30',
         'location': '제네바, 스위스', 'category': 'pain', 'type': 'intl',
         'source': 'EAN', 'url': 'https://www.ean.org'},
        {'name': 'IASP World Congress on Pain 2026 (세계통증학회)', 'start': f'{y}-10-26', 'end': f'{y}-10-30',
         'location': '방콕, 태국', 'category': 'pain', 'type': 'intl',
         'source': 'IASP', 'url': 'https://www.iasp-pain.org'},
    ]

    results = []
    for item in data:
        ev = make_event(item['name'], item['start'], item['end'],
                        item['location'], item['category'], item['type'],
                        item['source'], item['url'])
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
        # 주요 학회 사이트 (하반기 확정 일정 포함)
        crawl_hypertension,    # 대한고혈압학회 (CV)
        crawl_cardiology,      # 대한심장학회 (CV)
        crawl_neurology,       # 대한신경과학회 (Pain)
        crawl_diabetes,        # 대한당뇨병학회 (CV)
        crawl_nephrology,      # 대한신장학회 (CV)
        crawl_endocrinology,   # 대한내분비학회 (CV)
        crawl_anesthesia,      # 대한마취통증의학회 (Pain)
        crawl_neurosurgery,    # 대한신경외과학회 (Pain)
        crawl_pain,            # 대한통증학회 (Pain)
        crawl_rehabilitation,  # 대한재활의학회 (Pain)
        # 통합 소스 (상반기 국내 전체)
        crawl_healthmedia,     # 메디칼허브 (CV+Pain 월별)
        crawl_mediking,        # 메디킹 (CV+Pain 보조)
        # 해외학회 고정 데이터
        get_intl_conferences,  # 주요 해외학회 17개
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
    print(f"CV: {len([c for c in all_conferences if c['category']=='cv'])}건")
    print(f"Pain: {len([c for c in all_conferences if c['category']=='pain'])}건")
    print(f"국내: {len([c for c in all_conferences if c['type']=='domestic'])}건")
    print(f"국제: {len([c for c in all_conferences if c['type']=='intl'])}건")

if __name__ == '__main__':
    main()
