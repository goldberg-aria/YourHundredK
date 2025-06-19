#!/usr/bin/env python3

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any, Optional
import logging
import argparse
from decimal import Decimal, ROUND_HALF_UP

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StockDataValidator:
    """주식 데이터 검증을 위한 클래스"""
    
    @staticmethod
    def validate_price_data(df: pd.DataFrame) -> bool:
        """가격 데이터 검증
        
        Returns:
            bool: 데이터가 유효하면 True
        """
        if df.empty:
            logger.error("가격 데이터가 비어있습니다.")
            return False
            
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required_columns):
            logger.error(f"필수 컬럼이 누락되었습니다. 필요한 컬럼: {required_columns}")
            return False
            
        if df.isnull().any().any():
            logger.warning("데이터에 결측치가 있습니다.")
            return False
            
        return True

    @staticmethod
    def validate_dividend_data(dividends: pd.Series) -> bool:
        """배당 데이터 검증
        
        Returns:
            bool: 데이터가 유효하면 True
        """
        if dividends.empty:
            logger.warning("배당 데이터가 없습니다.")
            return True  # 배당이 없는 것은 유효할 수 있음
            
        if dividends.isnull().any():
            logger.error("배당 데이터에 결측치가 있습니다.")
            return False
            
        if (dividends < 0).any():
            logger.error("음수 배당이 존재합니다.")
            return False
            
        return True

class InvestmentSimulator:
    """투자 시뮬레이션을 위한 클래스"""
    
    def __init__(self, price_data: pd.DataFrame, dividends: pd.Series):
        self.price_data = price_data
        self.dividends = dividends
        self.reset_simulation()
        
        # 거래 비용 설정
        self.TRANSACTION_FEE_RATE = 0.0025  # 0.25% 거래 수수료
        self.DIVIDEND_TAX_RATE = 0.154      # 15.4% 배당세
        self.MIN_TRANSACTION_FEE = 0.50     # 최소 거래 수수료 ($0.50)
        self.MAX_DAILY_VOLUME_RATIO = 0.10  # 일일 거래량의 최대 10%까지만 거래 가능
        
    def reset_simulation(self):
        """시뮬레이션 변수 초기화"""
        self.total_shares = Decimal('0')
        self.total_invested = Decimal('0')
        self.total_dividends_received = Decimal('0')
        self.total_fees_paid = Decimal('0')
        self.total_taxes_paid = Decimal('0')
        self.transactions = []
        
    def _localize_date(self, date: datetime) -> pd.Timestamp:
        """날짜를 price_data의 시간대로 변환"""
        if isinstance(date, str):
            date = pd.Timestamp(date)
        elif isinstance(date, datetime):
            date = pd.Timestamp(date)
        
        # 이미 시간대가 있는 경우 변환
        if date.tzinfo is not None:
            if self.price_data.index.tz is not None:
                return date.tz_convert(self.price_data.index.tz)
            return date.tz_localize(None)
        
        # 시간대가 없는 경우 설정
        if self.price_data.index.tz is not None:
            return date.tz_localize(self.price_data.index.tz)
        return date
        
    def _get_price_on_date(self, date: datetime) -> float:
        """특정 날짜의 종가 반환"""
        date = self._localize_date(date)
        available_dates = self.price_data.index[self.price_data.index >= date]
        if available_dates.empty:
            raise ValueError(f"No trading data available after {date}")
        trading_date = available_dates[0]
        return float(self.price_data.loc[trading_date, 'Close'])
        
    def _get_next_month_first_trading_day(self, date: datetime) -> Optional[datetime]:
        """다음 달의 첫 거래일 반환. 없으면 None 반환"""
        date = self._localize_date(date)
        next_month = date + pd.DateOffset(months=1)
        next_month = next_month.replace(day=1)
        available_dates = self.price_data.index[self.price_data.index >= next_month]
        if available_dates.empty:
            return None
        return available_dates[0]
        
    def _calculate_monthly_dividends(self, date: datetime) -> Decimal:
        """해당 월의 배당금 계산"""
        date = self._localize_date(date)
        month_start = date.replace(day=1)
        month_end = (month_start + pd.DateOffset(months=1)) - pd.Timedelta(days=1)
        
        month_dividends = self.dividends[
            (self.dividends.index >= month_start) &
            (self.dividends.index <= month_end)
        ]
        
        total_dividends = Decimal('0')
        for div_date, div_amount in month_dividends.items():
            total_dividends += Decimal(str(div_amount)) * self.total_shares
            
        return total_dividends
        
    def _calculate_transaction_fee(self, amount: Decimal) -> Decimal:
        """거래 수수료 계산"""
        fee = amount * Decimal(str(self.TRANSACTION_FEE_RATE))
        return max(Decimal(str(self.MIN_TRANSACTION_FEE)), fee)
        
    def _calculate_dividend_tax(self, dividend_amount: Decimal) -> Decimal:
        """배당금 세금 계산"""
        return dividend_amount * Decimal(str(self.DIVIDEND_TAX_RATE))
        
    def _get_max_purchasable_shares(self, date: pd.Timestamp, available_cash: Decimal, price: Decimal) -> Decimal:
        """거래량 제한을 고려한 최대 구매 가능 주식 수 계산"""
        if 'Volume' not in self.price_data.columns:
            return Decimal('inf')
            
        daily_volume = Decimal(str(self.price_data.loc[date, 'Volume']))
        max_volume_shares = daily_volume * Decimal(str(self.MAX_DAILY_VOLUME_RATIO))
        max_cash_shares = available_cash / price
        
        return min(max_volume_shares, max_cash_shares)
        
    def _execute_trade(self, date: pd.Timestamp, cash_amount: Decimal, trade_type: str) -> Decimal:
        """거래 실행 (수수료 및 거래량 제한 고려)"""
        price = Decimal(str(self.price_data.loc[date, 'Close']))
        fee = self._calculate_transaction_fee(cash_amount)
        available_cash = cash_amount - fee
        
        if available_cash <= 0:
            return Decimal('0')
            
        max_shares = self._get_max_purchasable_shares(date, available_cash, price)
        actual_shares = min(
            max_shares,
            (available_cash / price).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
        )
        
        if actual_shares <= 0:
            return Decimal('0')
            
        actual_cost = (actual_shares * price) + fee
        self.total_shares += actual_shares
        self.total_fees_paid += fee
        
        self.transactions.append({
            'date': date,
            'type': trade_type,
            'amount': float(cash_amount),
            'shares': float(actual_shares),
            'price': float(price),
            'fee': float(fee)
        })
        
        return actual_cost
        
    def simulate(self, 
                initial_investment: float,
                monthly_investment: float,
                start_date: datetime,
                end_date: datetime,
                dividend_reinvestment: bool = True) -> Dict[str, Any]:
        """투자 시뮬레이션 실행
        
        Args:
            initial_investment: 초기 투자금
            monthly_investment: 월별 추가 투자금 (사용되지 않음)
            start_date: 시작일
            end_date: 종료일
            dividend_reinvestment: 배당금 재투자 여부
            
        Returns:
            Dict containing simulation results
        """
        self.reset_simulation()
        
        # 날짜를 price_data의 시간대로 변환
        start_date = self._localize_date(start_date)
        end_date = self._localize_date(end_date)
        
        # 초기 투자
        current_date = start_date
        initial_price = self._get_price_on_date(current_date)
        initial_shares = Decimal(str(initial_investment)) / Decimal(str(initial_price))
        
        # 거래 수수료 계산
        fee = max(
            initial_investment * self.TRANSACTION_FEE_RATE,
            self.MIN_TRANSACTION_FEE
        )
        
        self.total_shares = initial_shares
        self.total_invested = Decimal(str(initial_investment))
        self.total_fees_paid = Decimal(str(fee))
        
        # 거래 기록 추가
        self.transactions.append({
            'date': current_date,
            'action': 'BUY',
            'shares': float(initial_shares),
            'price': float(initial_price),
            'amount': float(initial_investment),
            'fee': float(fee)
        })
        
        # 매월 첫 거래일에 배당금 재투자
        while current_date <= end_date:
            # 해당 월의 배당금 계산
            month_dividends = self._calculate_monthly_dividends(current_date)
            
            if month_dividends > 0:
                # 배당세 계산
                dividend_tax = month_dividends * Decimal(str(self.DIVIDEND_TAX_RATE))
                net_dividends = month_dividends - dividend_tax
                self.total_taxes_paid += dividend_tax
                self.total_dividends_received += net_dividends
                
                if dividend_reinvestment and net_dividends > Decimal('5.0'):
                    # 배당금으로 주식 추가 매수
                    price = self._get_price_on_date(current_date)
                    fee = max(
                        net_dividends * Decimal(str(self.TRANSACTION_FEE_RATE)),
                        Decimal(str(self.MIN_TRANSACTION_FEE))
                    )
                    
                    if net_dividends > fee:
                        actual_investment = net_dividends - fee
                        actual_shares = actual_investment / Decimal(str(price))
                        self.total_shares += actual_shares
                        self.total_fees_paid += fee
                        
                        # 거래 기록 추가
                        self.transactions.append({
                            'date': current_date,
                            'action': 'REINVEST',
                            'shares': float(actual_shares),
                            'price': float(price),
                            'amount': float(actual_investment),
                            'fee': float(fee)
                        })
            
            # 다음 달의 첫 거래일로 이동
            next_date = self._get_next_month_first_trading_day(current_date)
            if next_date is None:
                break
            current_date = next_date
        
        # 최종 결과 계산
        final_price = self._get_price_on_date(end_date)
        final_value = self.total_shares * Decimal(str(final_price))
        
        # 순수 자본이득 (배당금 재투자로 인한 주식 증가분 제외)
        initial_value = initial_shares * Decimal(str(final_price))
        pure_capital_gain = initial_value - Decimal(str(initial_investment))
        pure_capital_gain_pct = (pure_capital_gain / Decimal(str(initial_investment))) * Decimal('100')
        
        # 배당금 재투자로 인한 추가 자본이득
        reinvestment_gain = final_value - initial_value
        total_gain = final_value - Decimal(str(initial_investment))
        
        # 연환산 수익률 계산
        annualized_return = 0
        duration_days = (end_date - start_date).days
        if duration_days > 0 and initial_investment > 0:
            duration_years = Decimal(duration_days) / Decimal('365.25')
            annualized_return = (float(final_value) / float(initial_investment)) ** (1 / float(duration_years)) - 1
        
        return {
            'initial_investment': float(initial_investment),
            'monthly_investment': float(monthly_investment),
            'total_invested': float(self.total_invested),
            'total_shares': float(self.total_shares),
            'final_share_price': float(final_price),
            'final_value': float(final_value),
            'pure_capital_gain': float(pure_capital_gain),
            'pure_capital_gain_pct': float(pure_capital_gain_pct),
            'reinvestment_gain': float(reinvestment_gain),
            'total_gain': float(total_gain),
            'total_gain_pct': float((total_gain / Decimal(str(initial_investment))) * Decimal('100')),
            'total_dividends_received': float(self.total_dividends_received),
            'total_taxes_paid': float(self.total_taxes_paid),
            'total_fees_paid': float(self.total_fees_paid),
            'annualized_return_pct': annualized_return * 100,
            'transactions': self.transactions
        }

class StockAnalyzer:
    """주식 분석을 위한 메인 클래스"""
    
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.validator = StockDataValidator()
        self.eastern_tz = pytz.timezone('America/New_York')
        
    def get_stock_data(self, start_date: datetime, end_date: datetime) -> Optional[Dict[str, Any]]:
        """주식 데이터를 가져오고 검증"""
        try:
            stock = yf.Ticker(self.ticker)
            
            # 날짜를 뉴욕 시간으로 변환
            start_date_et = self.eastern_tz.localize(
                start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            )
            end_date_et = self.eastern_tz.localize(
                end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            )
            
            # 히스토리 데이터 가져오기
            df = stock.history(start=start_date_et, end=end_date_et)
            
            # 데이터 검증
            if not self.validator.validate_price_data(df):
                return None
                
            # 배당 데이터 가져오기
            dividends = stock.dividends
            
            # 배당 데이터의 시간대를 ET로 변환
            if not dividends.empty:
                dividends.index = dividends.index.tz_localize(None)  # 먼저 시간대 정보 제거
                dividends.index = pd.to_datetime(dividends.index).tz_localize(self.eastern_tz)
            
            if not self.validator.validate_dividend_data(dividends):
                return None
                
            return {
                'price_data': df,
                'dividends': dividends,
                'info': stock.info
            }
            
        except Exception as e:
            logger.error(f"데이터 가져오기 실패: {str(e)}")
            return None
            
    def run_simulation(self, 
                      initial_investment: float,
                      monthly_investment: float,
                      start_date: datetime,
                      end_date: datetime,
                      dividend_reinvestment: bool = True) -> Optional[Dict[str, Any]]:
        """투자 시뮬레이션 실행"""
        stock_data = self.get_stock_data(start_date, end_date)
        if not stock_data:
            return None
            
        simulator = InvestmentSimulator(stock_data['price_data'], stock_data['dividends'])
        results = simulator.simulate(
            initial_investment=initial_investment,
            monthly_investment=monthly_investment,
            start_date=start_date,
            end_date=end_date,
            dividend_reinvestment=dividend_reinvestment
        )
        
        if not results:
            return None
            
        return results  # 시뮬레이터의 결과를 직접 반환

def format_currency(amount: float) -> str:
    """통화 형식으로 포맷팅"""
    return f"${amount:,.2f}"

def format_percentage(percentage: float) -> str:
    """퍼센트 형식으로 포맷팅"""
    return f"{percentage:.2f}%"

def print_simulation_results(results: Dict[str, Any]):
    """시뮬레이션 결과 출력"""
    print("\n=== 투자 시뮬레이션 결과 ===")
    print(f"종목: TSLY (YieldMax TSLA Option Income Strategy ETF)")
    print(f"초기 투자금: {format_currency(results['initial_investment'])}")
    print()
    
    print(f"보유 주식 수: {results['total_shares']:.2f}")
    print(f"현재 주가: {format_currency(results['final_share_price'])}")
    print(f"포트폴리오 가치: {format_currency(results['final_value'])}")
    print()
    
    print("=== 수익 분석 ===")
    print(f"순수 자본이득: {format_currency(results['pure_capital_gain'])} ({results['pure_capital_gain_pct']:.2f}%)")
    print(f"배당금 재투자 수익: {format_currency(results['reinvestment_gain'])}")
    print(f"총 수익: {format_currency(results['total_gain'])} ({results['total_gain_pct']:.2f}%)")
    print()
    
    print("=== 배당금 및 비용 ===")
    print(f"배당금 총액 (세전): {format_currency(results['total_dividends_received'] + results['total_taxes_paid'])}")
    print(f"배당세: {format_currency(results['total_taxes_paid'])}")
    print(f"배당금 총액 (세후): {format_currency(results['total_dividends_received'])}")
    print(f"거래 수수료: {format_currency(results['total_fees_paid'])}")
    print()
    
    print("=== 종합 평가 ===")
    print(f"총 수익률: {results['total_gain_pct']:.2f}%")
    print(f"연환산 수익률: {results['annualized_return_pct']:.2f}%")
    print()

    print("=== 거래 내역 ===")
    for tx in results['transactions']:
        print(f"{tx['date'].strftime('%Y-%m-%d')} - {tx['action']}: {tx['shares']:.2f} shares @ {format_currency(tx['price'])} (수수료: {format_currency(tx['fee'])})")

def main():
    parser = argparse.ArgumentParser(description='주식 투자 시뮬레이터')
    parser.add_argument('ticker', type=str, help='주식 티커 심볼 (예: TSLY)')
    parser.add_argument('--initial_investment', type=float, default=10000.0, help='초기 투자금 (기본값: $10,000)')
    parser.add_argument('--start_date', type=str, default='2020-06-19', help='시작일 (YYYY-MM-DD)')
    parser.add_argument('--end_date', type=str, default='2025-06-17', help='종료일 (YYYY-MM-DD)')
    parser.add_argument('--no_dividend_reinvestment', action='store_true', help='배당금 재투자 비활성화')
    
    args = parser.parse_args()
    
    try:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError as e:
        logger.error(f"날짜 형식이 잘못되었습니다: {e}")
        return
        
    analyzer = StockAnalyzer(args.ticker)
    stock_data = analyzer.get_stock_data(start_date, end_date)
    
    if stock_data:
        results = analyzer.run_simulation(
            initial_investment=args.initial_investment,
            monthly_investment=0.0,  # 월별 투자 제거
            start_date=start_date,
            end_date=end_date,
            dividend_reinvestment=not args.no_dividend_reinvestment
        )
        
        if results:
            print_simulation_results(results)
        else:
            logger.error(f"{args.ticker} 시뮬레이션 실패")
    else:
        logger.error(f"{args.ticker} 데이터 가져오기 실패")

if __name__ == "__main__":
    main() 