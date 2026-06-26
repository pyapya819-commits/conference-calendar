#!/usr/bin/env python3
import json
import re
import time
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
}
OUTPUT_PATH = Path(__file__).parent / 'data' / 'conferences.json'
CURRENT_YEAR = datetime.now().year
DELAY = 1.0

def get_soup(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        print(f"  HTTP {res.status_code}: {url}")
        if res.status_code != 200:
            return None
        res.encoding = res.apparent_encoding or 'utf-8'
        return BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        print(f"  오류: {e}")
        return None

def crawl_healthmedia():
    print("\n📡 메디칼허브 크롤링...")
    results = []

    cv_kw = ['고혈압', '심장', '심혈관', '당뇨', '내분비', '신장', '지질', '동맥경화',
             '심부전', '내과', 'TCTAP', '대사', '갑상선', '골다공증', '골대사',
             'SICEM', '부정맥', '심근경색', '뇌혈관', '심뇌혈관', '혈압', '순환기',
             '뇌졸중', '가정의학']
    pain_kw = ['정형외과', '신경외과', '마취', '통증', '재활', '척추', '관절',
               '신경과', '두통', '류마티스']
    exclude_kw = ['피부', '안과', '이비인후', '산부인과', '소아', '치과', '한의',
                  '정신', '흉부외과', '비뇨', '성형', '방사선', '병리',
                  '소화기', '위암', '간', '감염', '혈액', '종양', '폐암']

    urls = [
        ('3월', 'http://www.healthmedia.co.kr/news/articleView.html?idxno=104741'),
        ('4월',
