import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
import os
import pytz
import logging
import time
from functools import lru_cache
import random

load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API 요청 간 최소 대기 시간 (초)
MIN_REQUEST_DELAY = 2
MAX_REQUEST_DELAY = 5

def get_db_connection():
    """데이터베이스 연결을 생성합니다."""
    try:
        return psycopg2.connect(os.getenv('DATABASE_URL'))
    except Exception as e:
        logger.error(f"데이터베이스 연결 실패: {str(e)}")
        raise

def validate_date(date_str: str) -> str:
    """날짜가 유효한지 확인하고 적절한 형식으로 반환합니다."""
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        today = datetime.now(pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 미래 날짜는 어제 날짜로 조정
        if date.date() >= today.date():
            yesterday = (today - timedelta(days=1)).strftime('%Y-%m-%d')
            logger.info(f"미래 날짜 {date_str}를 {yesterday}로 조정")
            return yesterday
        return date_str
    except ValueError as e:
        logger.error(f"잘못된 날짜 형식: {date_str}, 오류: {str(e)}")
        yesterday = (datetime.now(pytz.UTC) - timedelta(days=1)).strftime('%Y-%m-%d')
        return yesterday

@lru_cache(maxsize=100)
def get_cached_stock_info(ticker: str) -> dict:
    """주식 정보를 캐시에서 가져오거나 API를 통해 가져옵니다."""
    max_retries = 3
    retry_delay = MIN_REQUEST_DELAY
    
    for attempt in range(max_retries):
        try:
            # API 요청 전 랜덤 딜레이
            time.sleep(random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY))
            
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if not info:
                raise ValueError(f"종목 {ticker}를 찾을 수 없습니다")
                
            return info
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"API 요청 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                time.sleep(retry_delay)
                retry_delay *= 2  # 지수 백오프
            else:
                logger.error(f"API 요청 최대 재시도 횟수 초과: {str(e)}")
                raise

def fetch_stock_data(ticker: str, start_date: str, end_date: str = None, force_refresh: bool = False):
    """주식 데이터를 가져와서 데이터베이스에 저장합니다. force_refresh가 True면 전체 구간을 새로 저장합니다."""
    try:
        # 날짜 유효성 검사
        start_date = validate_date(start_date)
        if end_date:
            end_date = validate_date(end_date)
            # 시작일이 종료일보다 이후면 교체
            if datetime.strptime(start_date, '%Y-%m-%d') > datetime.strptime(end_date, '%Y-%m-%d'):
                start_date, end_date = end_date, start_date
        else:
            end_date = (datetime.now(pytz.UTC) - timedelta(days=1)).strftime('%Y-%m-%d')

        # 시작일이 종료일보다 이후면 오류 발생
        if datetime.strptime(start_date, '%Y-%m-%d') > datetime.strptime(end_date, '%Y-%m-%d'):
            raise ValueError(f"시작일 {start_date}가 종료일 {end_date}보다 이후입니다")

        logger.info(f"{ticker} 데이터 가져오기: {start_date}부터 {end_date}까지 (force_refresh={force_refresh})")

        # 증분 저장: DB에서 마지막 저장 날짜 조회
        if not force_refresh:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT MAX(date) FROM stocks WHERE ticker = %s", (ticker,))
                        last_date = cur.fetchone()[0]
                        if last_date:
                            last_date_str = last_date.strftime('%Y-%m-%d')
                            # 만약 마지막 저장 날짜가 end_date보다 이전이면, 그 다음날부터만 추가
                            if last_date_str >= end_date:
                                logger.info(f"이미 {ticker}의 {start_date}~{end_date} 데이터가 모두 저장되어 있음.")
                                return True
                            # 시작일이 이미 저장된 마지막 날짜보다 이전이면, 그 다음날로 조정
                            if start_date <= last_date_str:
                                start_date = (datetime.strptime(last_date_str, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
                                logger.info(f"증분 저장: {start_date}부터 {end_date}까지 추가 저장")
            except Exception as e:
                logger.warning(f"마지막 저장 날짜 조회 실패: {str(e)} (무시하고 전체 저장 진행)")

        # 주식 정보 가져오기 (캐시 사용)
        try:
            stock_info = get_cached_stock_info(ticker)
        except Exception as e:
            logger.error(f"yfinance API 오류 ({ticker}): {str(e)}")
            raise ValueError(f"종목 {ticker}의 데이터를 가져오는데 실패했습니다")

        # 주가 데이터 가져오기
        try:
            time.sleep(random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY))
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            if hist.empty:
                logger.info(f"{ticker}의 {start_date}부터 {end_date}까지의 신규 데이터가 없습니다")
                return True
        except Exception as e:
            logger.error(f"주가 데이터 가져오기 실패 ({ticker}): {str(e)}")
            raise ValueError(f"{ticker}의 주가 데이터를 가져오는데 실패했습니다")

        # 배당금 데이터 가져오기
        try:
            time.sleep(random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY))
            dividends = stock.dividends.loc[start_date:end_date] if not stock.dividends.empty else pd.Series()
        except Exception as e:
            logger.warning(f"배당금 데이터 가져오기 실패 ({ticker}): {str(e)}")
            dividends = pd.Series()

        # 주식 분할 데이터 가져오기
        try:
            time.sleep(random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY))
            splits = stock.splits.loc[start_date:end_date] if not stock.splits.empty else pd.Series()
        except Exception as e:
            logger.warning(f"주식 분할 데이터 가져오기 실패 ({ticker}): {str(e)}")
            splits = pd.Series()

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # 주가 데이터 저장
                    stock_data = [(
                        ticker,
                        date.strftime('%Y-%m-%d'),
                        float(row['Close']),
                        int(row['Volume'])
                    ) for date, row in hist.iterrows()]

                    if stock_data:
                        execute_batch(cur,
                            """INSERT INTO stocks (ticker, date, close_price, volume)
                               VALUES (%s, %s, %s, %s)
                               ON CONFLICT (ticker, date) 
                               DO UPDATE SET close_price = EXCLUDED.close_price,
                                           volume = EXCLUDED.volume""",
                            stock_data)

                    # 배당금 데이터 저장
                    if not dividends.empty:
                        dividend_data = [(
                            ticker,
                            date.strftime('%Y-%m-%d'),
                            float(amount)
                        ) for date, amount in dividends.items()]

                        execute_batch(cur,
                            """INSERT INTO dividends (ticker, date, amount)
                               VALUES (%s, %s, %s)
                               ON CONFLICT (ticker, date)
                               DO UPDATE SET amount = EXCLUDED.amount""",
                            dividend_data)

                    # 주식 분할 데이터 저장
                    if not splits.empty:
                        split_data = [(
                            ticker,
                            date.strftime('%Y-%m-%d'),
                            float(ratio)
                        ) for date, ratio in splits.items()]

                        execute_batch(cur,
                            """INSERT INTO splits (ticker, date, ratio)
                               VALUES (%s, %s, %s)
                               ON CONFLICT (ticker, date)
                               DO UPDATE SET ratio = EXCLUDED.ratio""",
                            split_data)

                    conn.commit()
        except Exception as e:
            logger.error(f"데이터베이스 저장 실패 ({ticker}): {str(e)}")
            raise ValueError(f"{ticker}의 데이터를 저장하는데 실패했습니다")

        return True
    except Exception as e:
        logger.error(f"{ticker} 데이터 가져오기 실패: {str(e)}")
        return False

def get_stock_data(ticker: str, start_date: str, end_date: str = None):
    """데이터베이스에서 주식 데이터를 조회합니다."""
    try:
        start_date = validate_date(start_date)
        if end_date:
            end_date = validate_date(end_date)
            # 시작일이 종료일보다 이후면 교체
            if datetime.strptime(start_date, '%Y-%m-%d') > datetime.strptime(end_date, '%Y-%m-%d'):
                start_date, end_date = end_date, start_date
        else:
            end_date = datetime.now().strftime('%Y-%m-%d')

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT s.date, s.close_price, s.volume, 
                           COALESCE(d.amount, 0) as dividend,
                           COALESCE(sp.ratio, 1) as split_ratio
                    FROM stocks s
                    LEFT JOIN dividends d ON s.ticker = d.ticker AND s.date = d.date
                    LEFT JOIN splits sp ON s.ticker = sp.ticker AND s.date = sp.date
                    WHERE s.ticker = %s AND s.date BETWEEN %s AND %s
                    ORDER BY s.date
                """, (ticker, start_date, end_date))
                
                columns = ['date', 'close_price', 'volume', 'dividend', 'split_ratio']
                data = pd.DataFrame(cur.fetchall(), columns=columns)
                
                if data.empty:
                    raise ValueError(f"No data found for {ticker}")
                    
                return data
    except Exception as e:
        print(f"Error getting data for {ticker}: {str(e)}")
        return pd.DataFrame()

def calculate_returns(ticker: str, investment_amount: float, start_date: str, end_date: str = None):
    """투자 수익률을 계산합니다."""
    try:
        data = get_stock_data(ticker, start_date, end_date)
        if data.empty:
            return None
        
        initial_price = data.iloc[0]['close_price']
        current_price = data.iloc[-1]['close_price']
        
        # 주식 수량 계산 (분할 고려)
        shares = investment_amount / initial_price
        split_multiplier = data['split_ratio'].prod()
        current_shares = shares * split_multiplier
        
        # 배당금 계산
        total_dividends = (data['dividend'] * shares).sum()
        
        # 현재 가치
        current_value = current_shares * current_price + total_dividends
        
        # 수익률 계산
        total_return = (current_value - investment_amount) / investment_amount * 100
        
        return {
            'initial_investment': investment_amount,
            'current_value': current_value,
            'total_return_percentage': total_return,
            'total_dividends': total_dividends,
            'shares_owned': current_shares,
            'start_date': start_date,
            'end_date': end_date or datetime.now().strftime('%Y-%m-%d'),
            'initial_price': initial_price,
            'final_price': current_price
        }
    except Exception as e:
        print(f"Error calculating returns for {ticker}: {str(e)}")
        return None 