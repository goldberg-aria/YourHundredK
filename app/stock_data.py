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

# 데이터 최신성 체크 시간 (1시간)
DATA_FRESHNESS_HOURS = 1

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

def check_data_freshness(ticker: str) -> bool:
    """데이터가 1시간 이내에 업데이트되었는지 확인합니다."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 가장 최근 데이터의 업데이트 시간 확인
                cur.execute("""
                    SELECT MAX(date) as last_date, 
                           MAX(updated_at) as last_updated 
                    FROM stocks 
                    WHERE ticker = %s
                """, (ticker,))
                result = cur.fetchone()
                
                if not result or not result[0]:
                    logger.info(f"{ticker}: 데이터가 없어서 갱신이 필요합니다")
                    return False
                
                last_date, last_updated = result
                now = datetime.now(pytz.UTC)
                
                # updated_at이 없으면 date 기준으로 판단
                if last_updated:
                    time_diff = now - last_updated.replace(tzinfo=pytz.UTC)
                else:
                    # date 기준으로 1시간 전인지 확인 (거래 시간 고려)
                    last_date_utc = last_date.replace(tzinfo=pytz.UTC)
                    time_diff = now - last_date_utc
                
                hours_diff = time_diff.total_seconds() / 3600
                is_fresh = hours_diff < DATA_FRESHNESS_HOURS
                
                logger.info(f"{ticker}: 마지막 업데이트로부터 {hours_diff:.1f}시간 경과, 최신성: {is_fresh}")
                return is_fresh
                
    except Exception as e:
        logger.error(f"데이터 최신성 확인 중 오류 ({ticker}): {str(e)}")
        return False

def fetch_stock_data(ticker: str, start_date: str, end_date: str = None, force_refresh: bool = False):
    """주식 데이터를 가져와서 데이터베이스에 저장합니다. 
    force_refresh가 True면 전체 구간을 새로 저장합니다.
    데이터가 1시간 이상 지났으면 자동으로 갱신합니다."""
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

        logger.info(f"{ticker} 데이터 가져오기: {start_date}부터 {end_date}까지 (force_refresh={force_refresh})")

        # force_refresh가 True인 경우 기존 데이터 삭제
        if force_refresh:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        # 주가 데이터 삭제
                        cur.execute("""
                            DELETE FROM stocks 
                            WHERE ticker = %s 
                            AND date BETWEEN %s AND %s
                        """, (ticker, start_date, end_date))
                        
                        # 배당금 데이터 삭제
                        cur.execute("""
                            DELETE FROM dividends 
                            WHERE ticker = %s 
                            AND date BETWEEN %s AND %s
                        """, (ticker, start_date, end_date))
                        
                        conn.commit()
                        logger.info(f"{ticker}의 {start_date}~{end_date} 기존 데이터 삭제 완료")
            except Exception as e:
                logger.error(f"기존 데이터 삭제 중 오류: {str(e)}")
                raise

        # 데이터 최신성 체크 (force_refresh가 아닌 경우에만)
        if not force_refresh:
            is_fresh = check_data_freshness(ticker)
            if is_fresh:
                logger.info(f"{ticker}: 데이터가 최신 상태입니다 (1시간 이내)")
                return True
            else:
                logger.info(f"{ticker}: 데이터가 오래되어 갱신이 필요합니다 (1시간 이상 경과)")

        # 증분 저장: DB에서 마지막 저장 날짜 조회
        if not force_refresh:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        # 마지막 날짜와 실제 데이터 개수 모두 확인
                        cur.execute("SELECT MAX(date), COUNT(*) FROM stocks WHERE ticker = %s", (ticker,))
                        result = cur.fetchone()
                        last_date = result[0]
                        data_count = result[1]
                        
                        if last_date and data_count > 0:
                            last_date_str = last_date.strftime('%Y-%m-%d')
                            # 만약 마지막 저장 날짜가 end_date보다 이전이면, 그 다음날부터만 추가
                            if last_date_str >= end_date:
                                logger.info(f"이미 {ticker}의 {start_date}~{end_date} 데이터가 모두 저장되어 있음.")
                                return True
                            # 시작일이 이미 저장된 마지막 날짜보다 이전이면, 그 다음날로 조정
                            if start_date <= last_date_str:
                                start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                                logger.info(f"시작일을 마지막 저장 날짜 다음 날인 {start_date}로 조정")
                        else:
                            # DB에 데이터가 없으면 전체 구간 저장
                            logger.info(f"{ticker}의 DB 데이터가 없어서 전체 구간 저장을 진행합니다.")
            except Exception as e:
                logger.error(f"마지막 저장 날짜 조회 중 오류: {str(e)}")
                raise

        # API 요청 전 랜덤 딜레이
        time.sleep(random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY))

        # yfinance에서 데이터 가져오기
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty:
            logger.warning(f"{ticker}의 {start_date}~{end_date} 데이터가 없습니다")
            return False

        # 주가 데이터 저장
        stock_data = []
        for date, row in hist.iterrows():
            stock_data.append((
                ticker,
                date.strftime('%Y-%m-%d'),
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                int(row['Volume']),
                datetime.now(pytz.UTC)
            ))

        # 배당금 데이터 가져오기
        dividends = stock.dividends
        if not dividends.empty:
            dividend_data = []
            for date, amount in dividends.items():
                if start_date <= date.strftime('%Y-%m-%d') <= end_date:
                    dividend_data.append((
                        ticker,
                        date.strftime('%Y-%m-%d'),
                        float(amount),
                        datetime.now(pytz.UTC)
                    ))

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 주가 데이터 저장
                execute_batch(cur, """
                    INSERT INTO stocks (ticker, date, open, high, low, close, volume, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, date) 
                    DO UPDATE SET 
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        updated_at = EXCLUDED.updated_at
                """, stock_data)

                # 배당금 데이터 저장
                if not dividends.empty and dividend_data:
                    execute_batch(cur, """
                        INSERT INTO dividends (ticker, date, amount, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (ticker, date) 
                        DO UPDATE SET 
                            amount = EXCLUDED.amount,
                            updated_at = EXCLUDED.updated_at
                    """, dividend_data)

            conn.commit()
            logger.info(f"{ticker}의 {start_date}~{end_date} 데이터 저장 완료")
            return True

    except Exception as e:
        logger.error(f"{ticker} 데이터 가져오기 실패: {str(e)}")
        raise

def check_dividend_data(ticker: str, start_date: str, end_date: str):
    """데이터베이스에 저장된 배당금 데이터를 확인합니다."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT date, amount 
                    FROM dividends 
                    WHERE ticker = %s 
                    AND date BETWEEN %s AND %s 
                    ORDER BY date
                """, (ticker, start_date, end_date))
                
                results = cur.fetchall()
                
                logger.info(f"\n=== {ticker} DB 배당금 데이터 ===")
                if results:
                    logger.info("데이터베이스에 저장된 배당금:")
                    for date, amount in results:
                        logger.info(f"날짜: {date.strftime('%Y-%m-%d')}, 배당금: ${amount:.4f}")
                else:
                    logger.info("데이터베이스에 배당금 데이터가 없습니다.")
                logger.info("===========================\n")
                
                return results
    except Exception as e:
        logger.error(f"배당금 데이터 확인 중 오류: {str(e)}")
        return None

def get_stock_data(ticker: str, start_date: str, end_date: str = None):
    """데이터베이스에서 주식 데이터를 가져옵니다."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 주가 데이터 가져오기
                cur.execute("""
                    SELECT s.date, s.open, s.high, s.low, s.close, s.volume, 
                           COALESCE(d.amount, 0) as dividend
                    FROM stocks s
                    LEFT JOIN dividends d ON s.ticker = d.ticker AND s.date = d.date
                    WHERE s.ticker = %s 
                    AND s.date BETWEEN %s AND %s
                    ORDER BY s.date
                """, (ticker, start_date, end_date or start_date))
                
                # 결과를 DataFrame으로 변환
                columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'dividend']
                data = cur.fetchall()
                
                if not data:
                    logger.warning(f"No data found for {ticker}")
                    return pd.DataFrame(columns=columns)
                
                df = pd.DataFrame(data, columns=columns)
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                return df
                
    except Exception as e:
        logger.error(f"Error getting data for {ticker}: {str(e)}")
        return pd.DataFrame()

def calculate_returns(ticker: str, investment_amount: float, start_date: str, end_date: str = None):
    """투자 수익률을 계산합니다."""
    try:
        # 데이터 가져오기
        stock_data = get_stock_data(ticker, start_date, end_date)
        if stock_data.empty:
            logger.error(f"{ticker}의 데이터가 없습니다")
            return None

        # 날짜 정렬
        stock_data = stock_data.sort_index()

        # 초기값과 최종값
        initial_price = stock_data.iloc[0]['close']
        final_price = stock_data.iloc[-1]['close']
        
        # 보유 주식수
        shares = investment_amount / initial_price
        
        # 자본 이득
        capital_gains = (final_price - initial_price) * shares
        
        # 배당금 계산
        total_dividends = stock_data['dividend'].sum() * shares
        
        # 총 수익과 수익률
        total_return = capital_gains + total_dividends
        total_return_percentage = (total_return / investment_amount) * 100
        
        # 보유 기간 계산 (실제 개월 수)
        first_date = stock_data.index[0]
        last_date = stock_data.index[-1]
        
        logger.info(f"\n=== {ticker} 보유 기간 계산 ===")
        logger.info(f"시작일: {first_date.strftime('%Y-%m-%d')}")
        logger.info(f"종료일: {last_date.strftime('%Y-%m-%d')}")
        
        # 연, 월 차이 계산
        years_diff = last_date.year - first_date.year
        months_diff = last_date.month - first_date.month
        
        logger.info(f"연도 차이: {years_diff}")
        logger.info(f"월 차이: {months_diff}")
        
        # 총 개월 수 계산
        months_held = years_diff * 12 + months_diff
        logger.info(f"기본 개월 수: {months_held}")
        
        if last_date.day < first_date.day:
            months_held -= 1
            logger.info(f"일자 조정 후 개월 수: {months_held}")
        
        months_held = max(months_held + 1, 1)  # 최소 1개월, 현재 달 포함
        logger.info(f"최종 개월 수: {months_held}")
        logger.info("========================\n")
        
        # 월 평균 배당금 계산
        monthly_dividend = total_dividends / months_held
        
        # 연간 배당률 계산 (12개월 기준)
        annual_dividends = monthly_dividend * 12
        dividend_yield = (annual_dividends / investment_amount) * 100

        return {
            'ticker': ticker,
            'investment_amount': investment_amount,
            'shares': shares,
            'initial_price': initial_price,
            'final_price': final_price,
            'capital_gains': capital_gains,
            'total_dividends': total_dividends,
            'monthly_dividend': monthly_dividend,
            'total_return': total_return,
            'total_return_percentage': total_return_percentage,
            'dividend_yield': dividend_yield,
            'months_held': months_held,
            'start_date': first_date.strftime('%Y-%m-%d'),
            'end_date': last_date.strftime('%Y-%m-%d')
        }
    except Exception as e:
        logger.error(f"수익률 계산 중 오류: {str(e)}")
        return None 