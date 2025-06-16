# What'sYourHundredK

투자 시뮬레이션 웹 애플리케이션으로, 사용자가 주식/ETF, 투자금, 기간을 선택하여 과거 투자 수익률을 계산하고 시각화할 수 있습니다.

## 주요 기능

- 주식/ETF 과거 데이터 기반 투자 수익률 계산
- 배당금, 주식 분할 등 반영
- 차트 시각화 (Plotly.js)
- 싱글/컴페어 모드 지원
- 실시간 데이터 갱신

## 기술 스택

- Backend: Flask, PostgreSQL
- Frontend: Tailwind CSS, Plotly.js
- Data: yfinance API
- Python 3.11

## 설치 및 실행

1. 저장소 클론
```bash
git clone https://github.com/goldberg-aria/YourHundredK.git
cd YourHundredK
```

2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

3. 의존성 설치
```bash
pip install -r requirements.txt
```

4. 데이터베이스 설정
```bash
flask db upgrade
```

5. 서버 실행
```bash
flask run
```

## 라이선스

MIT License