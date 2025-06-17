import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import yfinance as yf
import os
import logging

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
def simulate_investment(ticker, initial_amount, monthly_amount, start_date, end_date, reinvest_dividends=False):
    """투자 시뮬레이션을 실행합니다."""
    hist, dividends = get_stock_data(ticker, start_date, end_date)
    
    if hist is None:
        return None, None
    
    # 월별 투자 시뮬레이션
    results = []
    dividend_results = []
    total_invested = initial_amount
    shares = initial_amount / hist.iloc[0]['Close'] if len(hist) > 0 else 0
    total_dividends = 0
    
    current_date = pd.to_datetime(start_date).tz_localize(hist.index.tz)
    end_date = pd.to_datetime(end_date).tz_localize(hist.index.tz)
    
    while current_date <= end_date:
        # 해당 날짜의 주가 찾기
        available_dates = hist.index[hist.index >= current_date]
        if len(available_dates) == 0:
            break
            
        trade_date = available_dates[0]
        price = hist.loc[trade_date, 'Close']
        
        # 월별 투자 (첫 달 제외)
        if current_date != pd.to_datetime(start_date).tz_localize(hist.index.tz):
            shares += monthly_amount / price
            total_invested += monthly_amount
        
        # 배당금 계산
        period_dividends = 0
        if not dividends.empty:
            period_div = dividends[
                (dividends.index >= current_date - timedelta(days=30)) & 
                (dividends.index < current_date)
            ]
            if len(period_div) > 0:
                period_dividends = period_div.sum() * shares
                total_dividends += period_dividends
                
                # 배당금 재투자
                if reinvest_dividends:
                    shares += period_dividends / price
        
        # 현재 가치 계산
        current_value = shares * price
        
        results.append({
            'date': current_date.tz_convert(None),  # timezone 제거
            'shares': shares,
            'price': price,
            'total_invested': total_invested,
            'current_value': current_value,
            'gain_loss': current_value - total_invested,
            'return_pct': ((current_value - total_invested) / total_invested) * 100,
            'dividends_received': period_dividends,
            'total_dividends': total_dividends
        })
        
        # 배당금 데이터 (차트용)
        if period_dividends > 0:
            dividend_results.append({
                'date': current_date.tz_convert(None),
                'dividends': period_dividends
            })
        
        # 다음 달로 이동
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    
    return pd.DataFrame(results), pd.DataFrame(dividend_results)

# 메인 앱
def main():
    st.title("💰 What's Your Hundred K?")
    st.markdown("**주식 투자 시뮬레이터** - 당신의 10만불이 얼마가 될 수 있을까요?")
    
    # 사이드바 설정
    st.sidebar.header("📊 투자 설정")
    
    # 세션 상태 초기화
    if 'selected_stock' not in st.session_state:
        st.session_state.selected_stock = None
    if 'custom_ticker' not in st.session_state:
        st.session_state.custom_ticker = ""
    
    # 🏢 인기 배당주 (5개)
    st.sidebar.subheader("🏢 배당주")
    dividend_stocks = ['AAPL', 'JNJ', 'KO', 'PG', 'ABBV']
    cols = st.sidebar.columns(3)
    for i, ticker in enumerate(dividend_stocks):
        col_idx = i % 3
        with cols[col_idx]:
            if st.button(ticker, key=f"div_stock_{ticker}", use_container_width=True):
                st.session_state.selected_stock = ticker
                st.session_state.custom_ticker = ""
    
    # 📈 인기 배당 ETF (5개)
    st.sidebar.subheader("📈 배당 ETF")
    dividend_etfs = ['SCHD', 'VYM', 'JEPI', 'DIVO', 'HDV']
    cols = st.sidebar.columns(3)
    for i, ticker in enumerate(dividend_etfs):
        col_idx = i % 3
        with cols[col_idx]:
            if st.button(ticker, key=f"div_etf_{ticker}", use_container_width=True):
                st.session_state.selected_stock = ticker
                st.session_state.custom_ticker = ""
    
    # 🎯 인기 커버드콜 ETF (5개)
    st.sidebar.subheader("🎯 커버드콜 ETF")
    covered_call_etfs = ['QYLD', 'XYLD', 'RYLD', 'JEPQ', 'QYLG']
    cols = st.sidebar.columns(3)
    for i, ticker in enumerate(covered_call_etfs):
        col_idx = i % 3
        with cols[col_idx]:
            if st.button(ticker, key=f"cc_etf_{ticker}", use_container_width=True):
                st.session_state.selected_stock = ticker
                st.session_state.custom_ticker = ""
    
    # 🌟 인기 개별종목 커버드콜 (5개)
    st.sidebar.subheader("🌟 개별종목 CC")
    individual_covered_calls = ['TSLY', 'NVDY', 'CONY', 'GOOY', 'APLY']
    cols = st.sidebar.columns(3)
    for i, ticker in enumerate(individual_covered_calls):
        col_idx = i % 3
        with cols[col_idx]:
            if st.button(ticker, key=f"ind_cc_{ticker}", use_container_width=True):
                st.session_state.selected_stock = ticker
                st.session_state.custom_ticker = ""
    
    # 구분선
    st.sidebar.markdown("---")
    
    # 직접 티커 입력
    st.sidebar.subheader("✍️ 직접 입력")
    custom_input = st.sidebar.text_input(
        "티커 심볼 입력 (예: NFLX, UBER)",
        value=st.session_state.custom_ticker,
        placeholder="티커를 입력하세요...",
        key="ticker_input"
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
        
        st.sidebar.success(f"✅ 선택된 종목: **{st.session_state.selected_stock}** ({stock_category})")
        selected_stock = st.session_state.selected_stock
    else:
        st.sidebar.info("👆 위에서 종목을 선택하거나 티커를 입력하세요")
        selected_stock = None
    
    st.sidebar.markdown("---")
    
    # 투자 금액 설정
    initial_amount = st.sidebar.number_input(
        "초기 투자 금액 ($)",
        min_value=100,
        max_value=1000000,
        value=100000,
        step=1000
    )
    
    monthly_amount = st.sidebar.number_input(
        "월별 추가 투자 ($)",
        min_value=0,
        max_value=10000,
        value=0,
        step=50
    )
    
    # 기간 설정
    col1, col2 = st.sidebar.columns(2)
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
    
    # 배당금 재투자 옵션 (기본값 False)
    reinvest_dividends = st.sidebar.checkbox("배당금 재투자", value=False)
    
    # 시뮬레이션 실행 조건 확인
    if not selected_stock:
        st.info("📊 좌측 사이드바에서 종목을 선택하고 '시뮬레이션 실행' 버튼을 누르세요!")
        return
    
    # 시뮬레이션 실행 버튼
    if st.sidebar.button("🚀 시뮬레이션 실행", type="primary"):
        if start_date >= end_date:
            st.error("시작 날짜는 종료 날짜보다 이전이어야 합니다.")
            return
        
        with st.spinner(f"{selected_stock} 데이터를 분석하는 중..."):
            results, dividend_data = simulate_investment(
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
        
        final_result = results.iloc[-1]
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                "총 투자금액",
                f"${final_result['total_invested']:,.0f}"
            )
        
        with col2:
            st.metric(
                "현재 가치",
                f"${final_result['current_value']:,.0f}",
                f"${final_result['gain_loss']:,.0f}"
            )
        
        with col3:
            st.metric(
                "수익률",
                f"{final_result['return_pct']:.2f}%"
            )
        
        with col4:
            st.metric(
                "총 배당금",
                f"${final_result['total_dividends']:,.0f}"
            )
        
        with col5:
            st.metric(
                "보유 주식 수",
                f"{final_result['shares']:.2f}"
            )
        
        # 차트 생성 (서브플롯 - 투자 성과 + 배당금 막대그래프)
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('투자 성과', '배당금 수익'),
            vertical_spacing=0.1,
            row_heights=[0.7, 0.3]
        )
        
        # 메인 차트 - 투자 성과
        fig.add_trace(
            go.Scatter(
                x=results['date'],
                y=results['total_invested'],
                mode='lines',
                name='총 투자금액',
                line=dict(color='blue', width=2),
                hovertemplate='날짜: %{x}<br>총 투자금액: $%{y:,.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=results['date'],
                y=results['current_value'],
                mode='lines',
                name='현재 가치',
                line=dict(color='green', width=2),
                fill='tonexty',
                hovertemplate='날짜: %{x}<br>현재 가치: $%{y:,.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # 배당금 막대 차트
        if not dividend_data.empty:
            fig.add_trace(
                go.Bar(
                    x=dividend_data['date'],
                    y=dividend_data['dividends'],
                    name='월별 배당금',
                    marker_color='orange',
                    opacity=0.7,
                    hovertemplate='날짜: %{x}<br>배당금: $%{y:,.2f}<extra></extra>'
                ),
                row=2, col=1
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
                row=2, col=1
            )
        
        # 차트 레이아웃 설정
        chart_title = f"{selected_stock} 투자 시뮬레이션"
        
        fig.update_layout(
            title=chart_title,
            height=700,
            hovermode='x unified',
            showlegend=True
        )
        
        fig.update_xaxes(title_text="날짜", row=2, col=1)
        fig.update_yaxes(title_text="금액 ($)", row=1, col=1)
        fig.update_yaxes(title_text="배당금 ($)", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 추가 정보
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 투자 요약")
            
            # 월평균 배당금 계산
            investment_months = max(1, (end_date - start_date).days / 30)
            monthly_avg_dividend = final_result['total_dividends'] / investment_months
            
            summary_data = {
                "항목": [
                    "투자 기간",
                    "총 투자 횟수",
                    "평균 주가",
                    "연평균 수익률",
                    "배당 수익률",
                    "월평균 배당금"
                ],
                "값": [
                    f"{(end_date - start_date).days}일",
                    f"{len(results)}회",
                    f"${results['price'].mean():.2f}",
                    f"{(final_result['return_pct'] / ((end_date - start_date).days / 365)):.2f}%",
                    f"{(final_result['total_dividends'] / final_result['total_invested'] * 100):.2f}%",
                    f"${monthly_avg_dividend:.2f}"
                ]
            }
            st.table(pd.DataFrame(summary_data))
        
        with col2:
            st.subheader("💡 투자 분석")
            
            # 분석 메시지
            if final_result['return_pct'] > 0:
                st.success(f"🎉 수익을 얻었습니다! (+{final_result['return_pct']:.2f}%)")
            else:
                st.error(f"📉 손실이 발생했습니다. ({final_result['return_pct']:.2f}%)")
            
            if final_result['total_dividends'] > 0:
                st.info(f"💰 배당금으로 ${final_result['total_dividends']:,.2f}를 받았습니다.")
                st.info(f"📊 월평균 배당금: ${monthly_avg_dividend:.2f}")
            else:
                st.warning("📊 이 기간 동안 배당금이 없었습니다.")
            
            if reinvest_dividends and final_result['total_dividends'] > 0:
                st.success("🔄 배당금 재투자로 복리 효과를 누렸습니다!")
        
        # 상세 데이터 테이블
        with st.expander("📊 상세 데이터 보기"):
            display_data = results[['date', 'total_invested', 'current_value', 'gain_loss', 'return_pct', 'dividends_received', 'total_dividends']].round(2)
            display_data.columns = ['날짜', '총 투자금', '현재 가치', '손익', '수익률(%)', '월 배당금', '누적 배당금']
            st.dataframe(display_data, use_container_width=True)

if __name__ == "__main__":
    main() 