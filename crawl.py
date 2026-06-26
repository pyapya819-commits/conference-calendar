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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
}
OUTPUT_PATH = Path(__file__).parent / 'data' / 'conferences.json'
TIMEOUT = 15
DELAY = 2.0
CURRENT_YEAR = datetime.now().year

def get_soup(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        res.encoding = res.apparent_encoding or 'utf-8'
        print(f"    HTTP {res.status_code}: {url}")
        if res.status_code != 200:
            return None
        return BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        print(f"    ⚠️ 접근 실패: {e}")
        return None

def make_event(name, start, end, location, category, event_type, source, url=''):
    if not start or not name or len(name) < 3:
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
# Viatris 타겟 학회 키워드 정의
# =====================

# CV 타겟 학회명 키워드
CV_SOCIETIES = [
    '고혈압', '심장학회', '심혈관', '당뇨병학회', '내분비학회', '신장학회',
    '지질동맥경화', '심부전학회', '부정맥학회', '심혈관중재', '순환기',
    '심근경색', '심뇌혈관', '당뇨발', '비만학회', '갑상선학회',
    '대사증후군', '골다공증', 'TCTAP', 'SoLA', 'SICEM',
]

# Pain 타겟 학회명 키워드
PAIN_SOCIETIES = [
    '정형외과학회', '신경외과학회', '마취통증', '통증학회', '재활의학회',
    '신경과학회', '두통학회', '뇌졸중학회', '척추', '관절',
    '류마티스학회', '근골격', '신경근육', '신경집중치료',
]

# 제외할 키워드 (관련 없는 과)
EXCLUDE = [
    '피부과', '안과', '이비인후', '산부인과', '소아', '치과', '한의',
    '정신건강', '흉부외과', '비뇨', '성형외과', '방사선', '병리',
    '소화기', '위암', '대장암', '간학', '감염학회', '폐암',
    '혈액학회', '종양내과', '응급의학',
]

def is_target(text):
    """Viatris 타겟 학회인지 확인"""
    # 제외 키워드 먼저 체크
    if any(ex in text for ex in EXCLUDE):
        return None
    if any(k in text for k in CV_SOCIETIES):
        return 'cv'
    if any(k in text for k in PAIN_SOCIETIES):
        return 'pain'
    return None

def parse_healthmedia_article(url, soup):
    """메디칼허브 기사 파싱 - 형식: 2026-07-03 학회명 주관학회 장소"""
    results = []
    if not soup:
        return results

    text = soup.get_text(separator='\n', strip=True)
    lines = text.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # "2026-MM-DD 학회명 주관학회 장소" 형식 매칭
        m = re.match(r'(2026-\d{2}-\d{2})\s+(.+)', line)
        if not m:
            continue

        date_str = m.group(1)
        rest = m.group(2).strip()

        # 너무 짧으면 스킵
        if len(rest) < 5:
            continue

        # 타겟 여부 확인
        category = is_target(rest)
        if not category:
            continue

        # 학회명 / 주관학회 / 장소 분리
        # 공백 2개 이상으로 구분되는 경우
        parts = re.split(r'\s{2,}', rest)
        if len(parts) >= 3:
            name = parts[0].strip()
            location = parts[-1].strip()
        elif len(parts) == 2:
            name = parts[0].strip()
            location = parts[1].strip()
        else:
            name = rest[:80]
            location = '장소 미정'

        # 이름이 너무 짧으면 스킵
        if len(name) < 4:
            continue

        # 국제학회 여부
        intl_kw = ['국제', 'International', 'World', 'Congress', 'Global', 'Asia']
        event_type = 'intl' if any(k in name for k in intl_kw) else 'domestic'

        ev = make_event(name, date_str, date_str, location, category, event_type, '메디칼허브', url)
        if ev:
            results.append(ev)
            print(f"    ✅ [{category.upper()}] {name} ({date_str}) / {location}")

    return results

def crawl_healthmedia():
    """메디칼허브 월별 학술일정 크롤링"""
    print("📡 메디칼허브 크롤링...")
    results = []

    # 알려진 월별 URL 목록 (새 달이 올라오면 추가)
    article_urls = [
        ('3월', 'http://www.healthmedia.co.kr/news/articleView.html?idxno=104741'),
        ('4월', 'http://www.healthmedia.co.kr/news/articleView.html?idxno=104995'),
        ('5월', 'http://www.healthmedia.co.kr/news/articleView.html?idxno=105283'),
        ('6월', 'http://www.healthmedia.co.kr/news/articleView.html?idxno=105605'),
        ('7월', 'http://www.healthmedia.co.kr/news/articleView.html?idxno=106062'),
    ]

    # 목록 페이지에서 새 기사 자동 탐색
    list_url = 'http://www.healthmedia.co.kr/news/articleList.html?sc_sub_section_code=S2N13&view_type=sm'
    soup = get_soup(list_url)
    if soup:
        known_ids = {u for _, u in article_urls}
        for a in soup.select('a[href*="articleView"]'):
            href = a.get('href', '')
            title = a.get_text(strip=True)
            if str(CURRENT_YEAR) in title and '학술일정' in title and '국내' in title:
                if not href.startswith('http'):
                    href = 'http://www.healthmedia.co.kr' + href
                if href not in known_ids:
                    article_urls.append(('자동발견', href))
                    known_ids.add(href)
                    print(f"  🔍 새 기사 발견: {title} → {href}")
        time.sleep(DELAY)

    # 각 기사 파싱
    seen = set()
    for month_label, url in article_urls:
        print(f"\n  📰 {month_label} 기사 파싱중...")
        soup = get_soup(url)
        if not soup:
            print(f"    ❌ 접근 실패 - 스킵")
            continue

        items = parse_healthmedia_article(url, soup)
        for ev in items:
            key = (ev['name'][:25], ev['start'])
            if key not in seen:
                seen.add(key)
                results.append(ev)

        time.sleep(DELAY)

    print(f"\n  → 총 {len(results)}건 수집")
    return results

# =====================
# 주요 해외학회 하드코딩
# =====================
def get_intl_conferences():
    print("📡 주요 해외학회 추가...")
    y = CURRENT_YEAR
    data = [
        # CV
        {'name': 'ACC 2026 (미국심장학회)', 'start': f'{y}-03-28', 'end': f'{y}-03-30',
         'location': '뉴올리언스, 미국', 'category': 'cv', 'type': 'intl', 'source': 'ACC'},
        {'name': 'ACC Asia 2026 + KSC 춘계', 'start': f'{y}-04-17', 'end': f'{y}-04-18',
         'location': '경주, 한국', 'category': 'cv', 'type': 'intl', 'source': 'ACC/KSC'},
        {'name': 'EHRA 2026 (유럽심장부정맥학회)', 'start': f'{y}-04-12', 'end': f'{y}-04-14',
         'location': '파리, 프랑스', 'category': 'cv', 'type': 'intl', 'source': 'ESC/EHRA'},
        {'name': 'ESC Heart Failure 2026', 'start': f'{y}-05-09', 'end': f'{y}-05-12',
         'location': '바르셀로나, 스페인', 'category': 'cv', 'type': 'intl', 'source': 'ESC'},
        {'name': 'TCTAP 2026 (관상동맥중재술 아시아태평양)', 'start': f'{y}-04-29', 'end': f'{y}-05-02',
         'location': '서울, 한국', 'category': 'cv', 'type': 'intl', 'source': 'TCTAP'},
        {'name': 'ESH 2026 (유럽고혈압학회)', 'start': f'{y}-05-28', 'end': f'{y}-05-31',
         'location': '유럽', 'category': 'cv', 'type': 'intl', 'source': 'ESH'},
        {'name': 'ESC Congress 2026 (유럽심장학회)', 'start': f'{y}-08-28', 'end': f'{y}-08-31',
         'location': '뮌헨, 독일', 'category': 'cv', 'type': 'intl', 'source': 'ESC'},
        {'name': 'JSH 2026 (일본고혈압학회)', 'start': f'{y}-10-10', 'end': f'{y}-10-12',
         'location': '일본', 'category': 'cv', 'type': 'intl', 'source': 'JSH'},
        {'name': 'ISH 2026 (국제고혈압학회)', 'start': f'{y}-10-22', 'end': f'{y}-10-25',
         'location': 'UAE', 'category': 'cv', 'type': 'intl', 'source': 'ISH'},
        {'name': 'TCT 2026 (경피적관상동맥중재술학회)', 'start': f'{y}-10-31', 'end': f'{y}-11-03',
         'location': '샌디에이고, 미국', 'category': 'cv', 'type': 'intl', 'source': 'TCT'},
        {'name': 'AHA Scientific Sessions 2026 (미국심장협회)', 'start': f'{y}-11-07', 'end': f'{y}-11-09',
         'location': '시카고, 미국', 'category': 'cv', 'type': 'intl', 'source': 'AHA'},
        # Pain
        {'name': 'PainConnect 2026 (AAPM 미국통증의학회)', 'start': f'{y}-03-05', 'end': f'{y}-03-08',
         'location': '솔트레이크시티, 미국', 'category': 'pain', 'type': 'intl', 'source': 'AAPM'},
        {'name': 'AAOS Annual Meeting 2026 (미국정형외과학회)', 'start': f'{y}-03-11', 'end': f'{y}-03-15',
         'location': '라스베이거스, 미국', 'category': 'pain', 'type': 'intl', 'source': 'AAOS'},
        {'name': 'AAN Annual Meeting 2026 (미국신경과학회)', 'start': f'{y}-04-18', 'end': f'{y}-04-22',
         'location': '시카고, 미국', 'category': 'pain', 'type': 'intl', 'source': 'AAN'},
        {'name': 'AANS Annual Meeting 2026 (미국신경외과학회)', 'start': f'{y}-05-01', 'end': f'{y}-05-04',
         'location': '샌안토니오, 미국', 'category': 'pain', 'type': 'intl', 'source': 'AANS'},
        {'name': 'AHS Annual Meeting 2026 (미국두통학회)', 'start': f'{y}-06-04', 'end': f'{y}-06-07',
         'location': '올랜도, 미국', 'category': 'pain', 'type': 'intl', 'source': 'AHS'},
        {'name': 'EAN Congress 2026 (유럽신경과학회)', 'start': f'{y}-06-27', 'end': f'{y}-06-30',
         'location': '제네바, 스위스', 'category': 'pain', 'type': 'intl', 'source': 'EAN'},
        {'name': 'IASP World Congress on Pain 2026 (세계통증학회)', 'start': f'{y}-10-26', 'end': f'{y}-10-30',
         'location': '방콕, 태국', 'category': 'pain', 'type': 'intl', 'source': 'IASP'},
    ]

    results = []
    for item in data:
        ev = make_event(
            item['name'], item['start'], item['end'],
            item['location'], item['category'], item['type'],
            item['source'], item.get('url', '')
        )
        if ev:
            results.append(ev)
            print(f"  ✅ [{item['category'].upper()}] {item['name']} ({item['start']})")

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
    print("\n" + "="*55)
    print(f"🏥 Viatris 학회 캘린더 크롤링")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55 + "\n")

    all_conferences = []

    # 1. 메디칼허브 (국내 학회 - 타겟 필터링)
    try:
        results = crawl_healthmedia()
        all_conferences.extend(results)
    except Exception as e:
        print(f"❌ 메디칼허브 오류: {e}")
        traceback.print_exc()

    time.sleep(DELAY)

    # 2. 해외학회 고정 데이터
    try:
        results = get_intl_conferences()
        all_conferences.extend(results)
    except Exception as e:
        print(f"❌ 해외학회 오류: {e}")

    # 저장
    all_conferences = deduplicate(all_conferences)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        'last_updated': datetime.now().strftime('%Y-%m-%d'),
        'total': len(all_conferences),
        'conferences': all_conferences
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*55}")
    print(f"✅ 완료! 총 {len(all_conferences)}건 저장")
    cv = [c for c in all_conferences if c['category'] == 'cv']
    pain = [c for c in all_conferences if c['category'] == 'pain']
    domestic = [c for c in all_conferences if c['type'] == 'domestic']
    intl = [c for c in all_conferences if c['type'] == 'intl']
    print(f"   CV: {len(cv)}건 | Pain: {len(pain)}건")
    print(f"   국내: {len(domestic)}건 | 국제: {len(intl)}건")
    print("="*55)

if __name__ == '__main__':
    main()
