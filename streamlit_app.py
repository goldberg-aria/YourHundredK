# Updated: 2025-06-18 03:15 KST - Force cache clear and redeploy
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import yfinance as yf
import os
import logging
import pytz
import numpy as np
from stock_analyzer import StockAnalyzer

# 페이지 설정
st.set_page_config(
    page_title="What's Your Hundred K? 💰",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        logger.error(f"Error fetching data for {ticker}: {e}")
        return None, None

def calculate_returns(values):
    """수익률 계산 함수"""
    returns = values.pct_change().fillna(0)
    cum_returns = (1 + returns).cumprod() - 1
    return returns, cum_returns

def simulate_investment(ticker, start_date, initial_investment, monthly_investment, reinvest_dividends=True):
    """개선된 stock_analyzer를 사용한 투자 시뮬레이션"""
    try:
        # StockAnalyzer 인스턴스 생성
        analyzer = StockAnalyzer(ticker)
        
        # 시뮬레이션 실행
        results = analyzer.run_simulation(
            initial_investment=initial_investment,
            monthly_investment=monthly_investment,
            start_date=start_date,
            end_date=datetime.now(),
            dividend_reinvestment=reinvest_dividends
        )
        
        if results is None:
            return None
        
        # Streamlit 앱에서 사용할 수 있는 형태로 데이터 변환
        # 거래 내역을 기반으로 월별 데이터 생성
        transactions = results['transactions']
        
        # 월별 데이터 생성
        monthly_data = []
        current_shares = 0
        total_invested = 0
        
        for tx in transactions:
            if tx['action'] == 'BUY':
                current_shares += tx['shares']
                total_invested += tx['amount']
            elif tx['action'] == 'REINVEST':
                current_shares += tx['shares']
                total_invested += tx['amount']
            
            monthly_data.append({
                'date': tx['date'],
                'total_invested': total_invested,
                'shares': current_shares,
                'price': tx['price'],
                'current_value': current_shares * tx['price'],
                'capital_gains': (current_shares * tx['price']) - total_invested
            })
        
        # 배당금 데이터 생성
        dividend_data = pd.DataFrame()
        if results['total_dividends_received'] > 0:
            # 간단한 배당금 분배 (실제로는 더 복잡하지만 시각화용)
            dividend_per_month = results['total_dividends_received'] / len(monthly_data)
            for i, data in enumerate(monthly_data):
                dividend_data = pd.concat([dividend_data, pd.DataFrame({
                    'date': [data['date']],
                    'dividends': [dividend_per_month]
                })])
        
        return {
            'results': pd.DataFrame(monthly_data),
            'dividend_data': dividend_data,
            'total_invested': results['total_invested'],
            'final_value': results['final_value'],
            'total_dividends_received': results['total_dividends_received'],
            'capital_gains': results['total_gain'],
            'capital_gain_rate': results['pure_capital_gain_pct'],
            'dividend_yield': (results['total_dividends_received'] / results['total_invested']) * 100,
            'total_return_pct': results['total_gain_pct'],
            'monthly_avg_dividend': results['total_dividends_received'] / len(monthly_data) if monthly_data else 0,
            'days_diff': (datetime.now() - start_date).days,
            'annualized_return': results['annualized_return_pct']
        }
        
    except Exception as e:
        logger.error(f"Error in simulation: {e}")
        return None

# CSS 스타일 추가
def load_css():
    st.markdown("""
    <style>
    .main > div {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 10px;
        margin: 5px 0;
    }
    .stMetric > div {
        font-size: 14px !important;
    }
    .stMetric > div > div {
        font-size: 18px !important;
    }
    .stButton > button {
        width: 100%;
        height: 2.5rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

# 메인 앱
def main():
    st.title("💰 What's Your Hundred K?")
    st.markdown("**주식 투자 시뮬레이터** - 당신의 10만불이 얼마가 될 수 있을까요?")
    
    # 세션 상태 초기화
    if 'selected_stock' not in st.session_state:
        st.session_state.selected_stock = None
    if 'custom_ticker' not in st.session_state:
        st.session_state.custom_ticker = ""
    
    # 메인 화면에 투자 설정
    st.header("📊 투자 설정")
    
    # 종목 선택 섹션
    st.subheader("🎯 종목 선택")
    
    # 🏢 인기 배당주 (5개)
    st.markdown("**🏢 배당주**")
    dividend_stocks = ['AAPL', 'JNJ', 'KO', 'PG', 'ABBV']
    cols = st.columns(5)
    for i, ticker in enumerate(dividend_stocks):
        with cols[i]:
            if st.button(ticker, key=f"div_stock_{ticker}", use_container_width=True):
                st.session_state.selected_stock = ticker
                st.session_state.custom_ticker = ""
    
    # 📈 인기 배당 ETF (5개)
    st.markdown("**📈 배당 ETF**")
    dividend_etfs = ['SCHD', 'VYM', 'JEPI', 'DIVO', 'HDV']
    cols = st.columns(5)
    for i, ticker in enumerate(dividend_etfs):
        with cols[i]:
            if st.button(ticker, key=f"div_etf_{ticker}", use_container_width=True):
                st.session_state.selected_stock = ticker
                st.session_state.custom_ticker = ""
    
    # 🎯 인기 커버드콜 ETF (5개)
    st.markdown("**🎯 커버드콜 ETF**")
    covered_call_etfs = ['QYLD', 'XYLD', 'RYLD', 'JEPQ', 'QYLG']
    cols = st.columns(5)
    for i, ticker in enumerate(covered_call_etfs):
        with cols[i]:
            if st.button(ticker, key=f"cc_etf_{ticker}", use_container_width=True):
                st.session_state.selected_stock = ticker
                st.session_state.custom_ticker = ""
    
    # 🌟 인기 개별종목 커버드콜 (5개)
    st.markdown("**🌟 개별종목 CC**")
    individual_covered_calls = ['TSLY', 'NVDY', 'CONY', 'GOOY', 'APLY']
    cols = st.columns(5)
    for i, ticker in enumerate(individual_covered_calls):
        with cols[i]:
            if st.button(ticker, key=f"ind_cc_{ticker}", use_container_width=True):
                st.session_state.selected_stock = ticker
                st.session_state.custom_ticker = ""
    
    # 직접 티커 입력
    st.markdown("**✍️ 직접 입력**")
    col1, col2 = st.columns([3, 1])
    with col1:
        custom_input = st.text_input(
            "티커 심볼 입력 (예: NFLX, UBER)",
            value=st.session_state.custom_ticker,
            placeholder="티커를 입력하세요...",
            key="ticker_input",
            label_visibility="collapsed"
        )
    
    if custom_input and custom_input != st.session_state.custom_ticker:
        st.session_state.custom_ticker = custom_input.upper()
        st.session_state.selected_stock = custom_input.upper()
    
    # 선택된 종목 표시
    if st.session_state.selected_stock:
        # 카테고리별 설명
        stock_category = ""
        if st.session_state.selected_stock in dividend_stocks:
            stock_category = "배당주"
        elif st.session_state.selected_stock in dividend_etfs:
            stock_category = "배당 ETF"
        elif st.session_state.selected_stock in covered_call_etfs:
            stock_category = "커버드콜 ETF"
        elif st.session_state.selected_stock in individual_covered_calls:
            stock_category = "개별종목 커버드콜"
        else:
            stock_category = "사용자 입력 종목"
        
        st.success(f"✅ 선택된 종목: **{st.session_state.selected_stock}** ({stock_category})")
        selected_stock = st.session_state.selected_stock
    else:
        st.info("👆 위에서 종목을 선택하거나 티커를 입력하세요")
        selected_stock = None
    
    st.divider()
    
    # 투자 설정 섹션
    st.subheader("💰 투자 설정")
    
    # 투자 금액 설정 - 가로로 배치
    col1, col2 = st.columns(2)
    with col1:
        initial_amount = st.number_input(
            "초기 투자 금액 ($)",
            min_value=100,
            max_value=1000000,
            value=100000,
            step=1000
        )
    
    with col2:
        monthly_amount = st.number_input(
            "월별 추가 투자 ($)",
            min_value=0,
            max_value=10000,
            value=0,
            step=50
        )
    
    # 기간 설정
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        start_date = st.date_input(
            "시작 날짜",
            value=datetime.now() - timedelta(days=365),
            max_value=datetime.now()
        )
    
    with col2:
        end_date = st.date_input(
            "종료 날짜",
            value=datetime.now(),
            max_value=datetime.now()
        )
    
    with col3:
        # 배당금 재투자 옵션 (기본값 False)
        reinvest_dividends = st.checkbox("배당금 재투자", value=False)
    
    # 시뮬레이션 실행 조건 확인
    if not selected_stock:
        st.info("📊 위에서 종목을 선택하고 '시뮬레이션 실행' 버튼을 누르세요!")
        return
    
    # 시뮬레이션 실행 버튼 - 중앙에 크게
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        simulate_button = st.button("🚀 시뮬레이션 실행", type="primary", use_container_width=True)
    
    if simulate_button:
        if start_date >= end_date:
            st.error("시작 날짜는 종료 날짜보다 이전이어야 합니다.")
            return
        
        with st.spinner(f"{selected_stock} 데이터를 분석하는 중..."):
            results = simulate_investment(
                selected_stock,
                start_date,
                initial_amount,
                monthly_amount,
                reinvest_dividends
            )
        
        if results is None:
            st.error("데이터를 가져올 수 없습니다. 다른 주식이나 기간을 시도해보세요.")
            return
        
        # 결과 표시
        st.header("📈 투자 결과")
        
        # 주요 지표 - 폰트 크기 조정을 위한 CSS 스타일 추가
        st.markdown("""
        <style>
        div[data-testid="metric-container"] {
            background-color: #f0f2f6;
            border: 1px solid #d0d0d0;
            padding: 5px;
            border-radius: 5px;
            margin: 5px 0;
        }
        div[data-testid="metric-container"] > div > div > div {
            font-size: 14px !important;
        }
        div[data-testid="metric-container"] > div > div > div[data-testid="metric-value"] {
            font-size: 18px !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        final_result = results['results'].iloc[-1]
        initial_result = results['results'].iloc[0]
        
        # 정확한 수익률 계산
        total_invested = final_result['total_invested']
        final_value = final_result['final_value']
        total_dividends = results['total_dividends_received']
        
        # 시작가와 종료가
        start_price = initial_result['price']
        end_price = final_result['price']
        
        # 실제 자본 이익률 (주가 변화만)
        capital_gain_rate = ((end_price - start_price) / start_price) * 100
        
        # 실제 배당 수익률 (총 배당금 / 총 투자금)
        dividend_yield_rate = (total_dividends / total_invested) * 100
        
        # 통합 수익률 (최종가치 - 총투자금) / 총투자금
        total_return_rate = ((final_value - total_invested) / total_invested) * 100
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            st.metric(
                "총 투자금액",
                f"${final_result['total_invested']:,.0f}"
            )
        
        with col2:
            st.metric(
                "현재 가치",
                f"${final_result['final_value']:,.0f}",
                f"${final_result['capital_gains']:,.0f}"
            )
        
        with col3:
            st.metric(
                "총 수익률",
                f"{total_return_rate:.2f}%"
            )
        
        with col4:
            st.metric(
                "연환산 수익률",
                f"{results['annualized_return']:.2f}%"
            )
        
        with col5:
            st.metric(
                "총 배당금",
                f"${total_dividends:,.0f}"
            )
        
        with col6:
            st.metric(
                "보유 주식 수",
                f"{final_result['shares']:.2f}"
            )
        
        # 차트 생성 (서브플롯 - 주가차트 + 투자 성과 + 배당금 막대그래프)
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=(f'{selected_stock} 주가 차트', '투자 성과', '배당금 수익'),
            vertical_spacing=0.08,
            row_heights=[0.4, 0.4, 0.2]
        )
        
        # 주가 차트 (첫 번째 서브플롯)
        fig.add_trace(
            go.Scatter(
                x=results['results']['date'],
                y=results['results']['price'],
                mode='lines',
                name='주가',
                line=dict(color='red', width=2),
                hovertemplate='날짜: %{x}<br>주가: $%{y:,.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        # 투자 성과 차트 (두 번째 서브플롯)
        fig.add_trace(
            go.Scatter(
                x=results['results']['date'],
                y=results['results']['total_invested'],
                mode='lines',
                name='총 투자금액',
                line=dict(color='blue', width=2),
                hovertemplate='날짜: %{x}<br>총 투자금액: $%{y:,.2f}<extra></extra>'
            ),
            row=2, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=results['results']['date'],
                y=results['results']['current_value'],
                mode='lines',
                name='현재 가치',
                line=dict(color='green', width=2),
                fill='tonexty',
                hovertemplate='날짜: %{x}<br>현재 가치: $%{y:,.2f}<extra></extra>'
            ),
            row=2, col=1
        )
        
        # 배당금 막대 차트 (세 번째 서브플롯)
        if not results['dividend_data'].empty:
            fig.add_trace(
                go.Bar(
                    x=results['dividend_data']['date'],
                    y=results['dividend_data']['dividends'],
                    name='월별 배당금',
                    marker_color='orange',
                    opacity=0.7,
                    hovertemplate='날짜: %{x}<br>배당금: $%{y:,.2f}<extra></extra>'
                ),
                row=3, col=1
            )
        else:
            # 배당금이 없는 경우 빈 차트
            fig.add_trace(
                go.Bar(
                    x=[],
                    y=[],
                    name='배당금 없음',
                    marker_color='lightgray'
                ),
                row=3, col=1
            )
        
        # 차트 레이아웃 설정
        chart_title = f"{selected_stock} 투자 시뮬레이션"
        
        fig.update_layout(
            title=chart_title,
            height=900,  # 3개 차트를 위해 높이 증가
            hovermode='x unified',
            showlegend=True
        )
        
        fig.update_xaxes(title_text="날짜", row=3, col=1)
        fig.update_yaxes(title_text="주가 ($)", row=1, col=1)
        fig.update_yaxes(title_text="금액 ($)", row=2, col=1)
        fig.update_yaxes(title_text="배당금 ($)", row=3, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 추가 정보
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 투자 요약")
            
            # 월평균 배당금 계산
            investment_months = max(1, (end_date - start_date).days / 30)
            monthly_avg_dividend = total_dividends / investment_months
            
            # 기간 계산
            investment_days = (end_date - start_date).days
            investment_months_count = len(results['results'])
            
            # 연환산 수익률
            if investment_days > 0:
                annualized_return = ((final_value / total_invested) ** (365 / investment_days) - 1) * 100
            else:
                annualized_return = 0
            
            # 평균 주가 계산
            avg_price = results['results']['price'].mean()
            
            summary_data = {
                "항목": [
                    "투자 기간",
                    "총 투자 횟수",
                    "평균 주가",
                    "시세차익 수익률",
                    "배당 수익률",
                    "🎯 통합 수익률",
                    "연환산 통합 수익률",
                    "월평균 배당금"
                ],
                "값": [
                    f"{investment_days}일",
                    f"{investment_months_count}회",
                    f"${avg_price:.2f}",
                    f"{capital_gain_rate:.2f}%",
                    f"{dividend_yield_rate:.2f}%",
                    f"{total_return_rate:.2f}%",
                    f"{results['annualized_return']:.2f}%",
                    f"${monthly_avg_dividend:.2f}"
                ]
            }
            st.table(pd.DataFrame(summary_data))
        
        with col2:
            st.subheader("💡 투자 분석")
            
            # 분석 메시지
            if total_return_rate > 0:
                st.success(f"🎉 통합 수익률: +{total_return_rate:.2f}%")
                st.success(f"💰 총 수익: ${final_value - total_invested:,.0f}")
            else:
                st.error(f"📉 통합 수익률: {total_return_rate:.2f}%")
                st.error(f"💸 총 손실: ${final_value - total_invested:,.0f}")
            
            # 수익 구성 분석
            st.markdown("**📊 수익 구성:**")
            st.markdown(f"- 시세차익: ${final_value - total_invested - total_dividends:,.0f} ({capital_gain_rate:.2f}%)")
            st.markdown(f"- 배당수익: ${total_dividends:,.0f} ({dividend_yield_rate:.2f}%)")
            
            if total_dividends > 0:
                st.info(f"월평균 배당금: ${monthly_avg_dividend:.2f}")
            else:
                st.warning("📊 이 기간 동안 배당금이 없었습니다.")
            
            if reinvest_dividends and total_dividends > 0:
                st.success("🔄 배당금 재투자로 복리 효과를 누렸습니다!")
        
        # 상세 데이터 테이블
        with st.expander("📊 상세 데이터 보기"):
            display_data = results['results'][['date', 'total_invested', 'current_value', 'capital_gains', 'dividend_yield']].round(2)
            display_data.columns = ['날짜', '총 투자금', '현재 가치', '시세차익', '배당 수익률(%)']
            st.dataframe(display_data, use_container_width=True)

if __name__ == "__main__":
    main() 