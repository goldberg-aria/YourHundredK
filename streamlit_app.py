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

def simulate_investment(ticker, initial_amount, monthly_amount, start_date, end_date, reinvest_dividends=False):
    """투자 시뮬레이션을 실행합니다."""
    hist, dividends = get_stock_data(ticker, start_date, end_date)
    
    if hist is None or hist.empty:
        return None, None
    
    # UTC 타임존으로 통일
    utc = pytz.UTC
    
    # 날짜를 pandas Timestamp로 변환하고 UTC로 설정
    start_ts = pd.Timestamp(start_date).tz_localize(utc)
    end_ts = pd.Timestamp(end_date).tz_localize(utc)
    
    # 히스토리 데이터의 타임존을 UTC로 변환
    if hist.index.tz is not None:
        hist.index = hist.index.tz_convert(utc)
    else:
        hist.index = hist.index.tz_localize(utc)
    
    # 배당금 데이터의 타임존도 UTC로 변환
    if not dividends.empty:
        if dividends.index.tz is not None:
            dividends.index = dividends.index.tz_convert(utc)
        else:
            dividends.index = dividends.index.tz_localize(utc)
    
    # 시작일과 종료일에 해당하는 주가 찾기
    start_price_date = hist.index[hist.index >= start_ts].min()
    end_price_date = hist.index[hist.index <= end_ts].max()
    
    if pd.isna(start_price_date) or pd.isna(end_price_date):
        return None, None
    
    start_price = hist.loc[start_price_date, 'Close']
    end_price = hist.loc[end_price_date, 'Close']
    
    # 배당금 필터링 (시작일과 종료일 사이)
    period_dividends = dividends[(dividends.index >= start_ts) & (dividends.index <= end_ts)]
    
    # 단순한 투자 시뮬레이션
    # 1. 초기 투자로 주식 구매
    initial_shares = initial_amount / start_price
    total_shares = initial_shares
    total_invested = initial_amount
    
    # 2. 투자 기간 동안의 총 배당금 계산 (초기 주식 수 기준)
    total_dividend_per_share = period_dividends.sum() if not period_dividends.empty else 0
    total_dividends_received = total_dividend_per_share * initial_shares
    
    # 3. 배당금 재투자 (평균 주가로 계산)
    if reinvest_dividends and total_dividends_received > 0:
        # 투자 기간 평균 주가로 배당금 재투자
        avg_price = hist.loc[start_price_date:end_price_date, 'Close'].mean()
        reinvested_shares = total_dividends_received / avg_price
        total_shares += reinvested_shares
    
    # 4. 월별 추가 투자 시뮬레이션
    monthly_additions = 0
    if monthly_amount > 0:
        # 대략적인 월수 계산
        days_diff = (end_ts - start_ts).days
        months = max(1, round(days_diff / 30))
        monthly_additions = (months - 1) * monthly_amount  # 첫 달 제외
        total_invested += monthly_additions
        
        # 평균 주가로 월별 투자 계산
        avg_price = hist.loc[start_price_date:end_price_date, 'Close'].mean()
        additional_shares = monthly_additions / avg_price
        total_shares += additional_shares
    
    # 5. 최종 결과 계산
    final_value = total_shares * end_price
    total_gain_loss = final_value - total_invested
    total_return_pct = (total_gain_loss / total_invested) * 100
    
    # 6. 수익 구성 분석
    # 시세차익 = (종료가 - 시작가) × 초기주식수 + 추가투자 시세차익
    capital_gains = (end_price - start_price) * initial_shares
    if monthly_additions > 0:
        # 평균 매수가 기준으로 추가 시세차익 계산
        avg_buy_price = (initial_amount + monthly_additions) / (initial_shares + additional_shares)
        additional_capital_gains = (end_price - avg_buy_price) * additional_shares
        capital_gains += additional_capital_gains
    
    # 배당 수익률
    dividend_yield = (total_dividends_received / total_invested) * 100
    capital_gain_rate = (capital_gains / total_invested) * 100
    
    # 간단한 월별 데이터 생성 (시각화용)
    results = []
    dividend_results = []
    
    # 월별 데이터를 12개월로 나누어 생성
    days_diff = (end_ts - start_ts).days
    months = max(12, round(days_diff / 30))
    
    for i in range(months):
        # 각 월의 날짜 계산
        if start_ts.month + i <= 12:
            month_date = start_ts.replace(month=start_ts.month + i)
        else:
            years_add = (start_ts.month + i - 1) // 12
            month_num = ((start_ts.month + i - 1) % 12) + 1
            month_date = start_ts.replace(year=start_ts.year + years_add, month=month_num)
        
        if month_date > end_ts:
            break
            
        # 해당 월의 주가 찾기
        month_prices = hist[hist.index <= month_date]
        if month_prices.empty:
            continue
            
        current_price = month_prices.iloc[-1]['Close']
        price_date = month_prices.index[-1]
        
        # 월별 투자금 누적
        monthly_invested = initial_amount + (i * monthly_amount if i > 0 else 0)
        
        # 해당 시점까지의 배당금
        month_dividends = period_dividends[period_dividends.index <= month_date].sum() * initial_shares
        
        # 월별 포트폴리오 가치
        current_shares = initial_shares + (i * monthly_amount / current_price if i > 0 and monthly_amount > 0 else 0)
        current_value = current_shares * current_price
        
        results.append({
            'date': price_date.tz_convert(None),
            'shares': current_shares,
            'price': current_price,
            'total_invested': monthly_invested,
            'current_value': current_value,
            'gain_loss': current_value - monthly_invested,
            'return_pct': ((current_value - monthly_invested) / monthly_invested) * 100,
            'dividends_received': month_dividends / months if months > 0 else 0,  # 월평균
            'total_dividends': month_dividends
        })
        
        # 배당금이 있는 월만 차트에 표시
        if i < len(period_dividends) and not period_dividends.empty:
            dividend_results.append({
                'date': price_date.tz_convert(None),
                'dividends': month_dividends / months if months > 0 else 0
            })
    
    # 디버깅 정보
    st.write(f"**{ticker} 계산 요약:**")
    st.write(f"- 투자기간: {days_diff}일")
    st.write(f"- 시작가: ${start_price:.2f}")
    st.write(f"- 종료가: ${end_price:.2f}")
    st.write(f"- 주가변동: {((end_price - start_price) / start_price * 100):.2f}%")
    st.write(f"- 총 배당금/주: ${total_dividend_per_share:.4f}")
    st.write(f"- 배당금 횟수: {len(period_dividends)}회")
    st.write(f"- 시세차익 수익률: {capital_gain_rate:.2f}%")
    st.write(f"- 배당 수익률: {dividend_yield:.2f}%")
    st.write(f"- 총 수익률: {total_return_pct:.2f}%")
    
    return pd.DataFrame(results), pd.DataFrame(dividend_results)

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
        initial_result = results.iloc[0]
        
        # 정확한 수익률 계산
        total_invested = final_result['total_invested']
        final_value = final_result['current_value']
        total_dividends = final_result['total_dividends']
        
        # 시작가와 종료가
        start_price = initial_result['price']
        end_price = final_result['price']
        
        # 실제 자본 이익률 (주가 변화만)
        capital_gain_rate = ((end_price - start_price) / start_price) * 100
        
        # 실제 배당 수익률 (총 배당금 / 총 투자금)
        dividend_yield_rate = (total_dividends / total_invested) * 100
        
        # 통합 수익률 (최종가치 - 총투자금) / 총투자금
        total_return_rate = ((final_value - total_invested) / total_invested) * 100
        
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
                f"{total_return_rate:.2f}%"
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
            
            # 기간 계산
            investment_days = (end_date - start_date).days
            investment_months_count = len(results)
            
            # 연환산 수익률
            if investment_days > 0:
                annualized_return = ((final_value / total_invested) ** (365 / investment_days) - 1) * 100
            else:
                annualized_return = 0
            
            # 평균 주가 계산
            avg_price = results['price'].mean()
            
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
                    f"{annualized_return:.2f}%",
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
            
            if final_result['total_dividends'] > 0:
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