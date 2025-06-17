import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yfinance as yf
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_batch
import logging

# 환경변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="What's Your Hundred K? 💰",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터베이스 연결 함수
@st.cache_resource
def get_db_connection():
    """데이터베이스 연결을 생성합니다."""
    try:
        return psycopg2.connect(os.getenv('DATABASE_URL'))
    except Exception as e:
        st.error(f"데이터베이스 연결 실패: {str(e)}")
        return None

# 주식 데이터 가져오기 함수
@st.cache_data(ttl=3600)  # 1시간 캐시
def get_stock_data(ticker, start_date, end_date):
    """주식 데이터를 가져옵니다."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date)
        dividends = stock.dividends
        
        if hist.empty:
            return None, None
            
        return hist, dividends
    except Exception as e:
        logger.error(f"주식 데이터 가져오기 오류 ({ticker}): {str(e)}")
        return None, None

# 투자 시뮬레이션 함수
def simulate_investment(ticker, initial_amount, monthly_amount, start_date, end_date, reinvest_dividends=True):
    """투자 시뮬레이션을 실행합니다."""
    hist, dividends = get_stock_data(ticker, start_date, end_date)
    
    if hist is None:
        return None
    
    # 월별 투자 시뮬레이션
    results = []
    total_invested = initial_amount
    shares = initial_amount / hist.iloc[0]['Close'] if len(hist) > 0 else 0
    
    current_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    while current_date <= end_date:
        # 해당 날짜의 주가 찾기
        available_dates = hist.index[hist.index >= current_date]
        if len(available_dates) == 0:
            break
            
        trade_date = available_dates[0]
        price = hist.loc[trade_date, 'Close']
        
        # 월별 투자 (첫 달 제외)
        if current_date != pd.to_datetime(start_date):
            shares += monthly_amount / price
            total_invested += monthly_amount
        
        # 배당금 재투자
        if reinvest_dividends and not dividends.empty:
            period_dividends = dividends[
                (dividends.index >= current_date - timedelta(days=30)) & 
                (dividends.index < current_date)
            ]
            if len(period_dividends) > 0:
                dividend_amount = period_dividends.sum() * shares
                shares += dividend_amount / price
        
        # 현재 가치 계산
        current_value = shares * price
        
        results.append({
            'date': current_date,
            'shares': shares,
            'price': price,
            'total_invested': total_invested,
            'current_value': current_value,
            'gain_loss': current_value - total_invested,
            'return_pct': ((current_value - total_invested) / total_invested) * 100
        })
        
        # 다음 달로 이동
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    
    return pd.DataFrame(results)

# 메인 앱
def main():
    st.title("💰 What's Your Hundred K?")
    st.markdown("**주식 투자 시뮬레이터** - 당신의 10만원이 얼마가 될 수 있을까요?")
    
    # 사이드바 설정
    st.sidebar.header("📊 투자 설정")
    
    # 주식 선택
    popular_stocks = {
        'AAPL': 'Apple Inc.',
        'MSFT': 'Microsoft Corp.',
        'GOOGL': 'Alphabet Inc.',
        'AMZN': 'Amazon.com Inc.',
        'TSLA': 'Tesla Inc.',
        'NVDA': 'NVIDIA Corp.',
        'META': 'Meta Platforms Inc.',
        'JNJ': 'Johnson & Johnson',
        'PG': 'Procter & Gamble',
        'KO': 'Coca-Cola Company'
    }
    
    selected_stock = st.sidebar.selectbox(
        "주식 선택",
        options=list(popular_stocks.keys()),
        format_func=lambda x: f"{x} - {popular_stocks[x]}",
        index=0
    )
    
    # 투자 금액 설정
    initial_amount = st.sidebar.number_input(
        "초기 투자 금액 ($)",
        min_value=100,
        max_value=1000000,
        value=1000,
        step=100
    )
    
    monthly_amount = st.sidebar.number_input(
        "월별 추가 투자 ($)",
        min_value=0,
        max_value=10000,
        value=100,
        step=50
    )
    
    # 기간 설정
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "시작 날짜",
            value=datetime.now() - timedelta(days=365*5),
            max_value=datetime.now()
        )
    
    with col2:
        end_date = st.date_input(
            "종료 날짜",
            value=datetime.now(),
            max_value=datetime.now()
        )
    
    # 배당금 재투자 옵션
    reinvest_dividends = st.sidebar.checkbox("배당금 재투자", value=True)
    
    # 시뮬레이션 실행 버튼
    if st.sidebar.button("🚀 시뮬레이션 실행", type="primary"):
        if start_date >= end_date:
            st.error("시작 날짜는 종료 날짜보다 이전이어야 합니다.")
            return
        
        with st.spinner(f"{selected_stock} 데이터를 분석하는 중..."):
            results = simulate_investment(
                selected_stock, 
                initial_amount, 
                monthly_amount, 
                start_date, 
                end_date, 
                reinvest_dividends
            )
        
        if results is None or results.empty:
            st.error("데이터를 가져올 수 없습니다. 다른 주식이나 기간을 시도해보세요.")
            return
        
        # 결과 표시
        st.header("📈 투자 결과")
        
        # 주요 지표
        final_result = results.iloc[-1]
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "총 투자금액",
                f"${final_result['total_invested']:,.2f}"
            )
        
        with col2:
            st.metric(
                "현재 가치",
                f"${final_result['current_value']:,.2f}",
                f"${final_result['gain_loss']:,.2f}"
            )
        
        with col3:
            st.metric(
                "수익률",
                f"{final_result['return_pct']:.2f}%"
            )
        
        with col4:
            st.metric(
                "보유 주식 수",
                f"{final_result['shares']:.4f}"
            )
        
        # 차트 생성
        fig = go.Figure()
        
        # 투자 금액 라인
        fig.add_trace(go.Scatter(
            x=results['date'],
            y=results['total_invested'],
            mode='lines',
            name='총 투자금액',
            line=dict(color='blue', width=2)
        ))
        
        # 현재 가치 라인
        fig.add_trace(go.Scatter(
            x=results['date'],
            y=results['current_value'],
            mode='lines',
            name='현재 가치',
            line=dict(color='green', width=2),
            fill='tonexty'
        ))
        
        fig.update_layout(
            title=f"{selected_stock} 투자 시뮬레이션 결과",
            xaxis_title="날짜",
            yaxis_title="금액 ($)",
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 상세 데이터 테이블
        with st.expander("📊 상세 데이터 보기"):
            st.dataframe(
                results[['date', 'total_invested', 'current_value', 'gain_loss', 'return_pct']].round(2),
                use_container_width=True
            )

if __name__ == "__main__":
    main() 