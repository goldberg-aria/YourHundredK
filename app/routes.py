from flask import Blueprint, jsonify, request, render_template
from flask_jwt_extended import jwt_required, create_access_token
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime
from .stock_data import fetch_stock_data, calculate_returns, get_stock_data
import pandas as pd

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/api/fetch-stock-data', methods=['POST'])
def api_fetch_stock_data():
    """주식 데이터를 가져와서 데이터베이스에 저장합니다."""
    try:
        data = request.json
        ticker = data.get('ticker')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        force_refresh = data.get('force_refresh', False)
        
        if not ticker or not start_date:
            return jsonify({'error': 'Ticker and start_date are required'}), 400
        
        success = fetch_stock_data(ticker, start_date, end_date, force_refresh=force_refresh)
        if success:
            return jsonify({'message': 'Data fetched and stored successfully'})
        else:
            return jsonify({'error': f'Failed to fetch data for {ticker}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/get-chart-data', methods=['POST'])
def api_get_chart_data():
    """차트용 데이터를 반환합니다."""
    try:
        data = request.json
        ticker = data.get('ticker')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        force_refresh = data.get('force_refresh', False)
        
        if not ticker or not start_date:
            return jsonify({'error': 'Ticker and start_date are required'}), 400
        
        # 데이터 가져오기 시도
        stock_data = get_stock_data(ticker, start_date, end_date)
        
        # 데이터가 없거나 force_refresh가 True면 새로 가져오기
        if stock_data.empty or force_refresh:
            success = fetch_stock_data(ticker, start_date, end_date, force_refresh=True)
            if success:
                stock_data = get_stock_data(ticker, start_date, end_date)
            else:
                return jsonify({'error': f'Failed to fetch data for {ticker}'}), 400
        
        if stock_data.empty:
            return jsonify({'error': f'No data available for {ticker}'}), 400
        
        # 배당금 데이터 로깅 추가
        print(f"\n=== {ticker} 배당금 데이터 ===")
        print("배당금이 있는 날짜:")
        dividend_data = stock_data[stock_data['dividend'] > 0]
        if not dividend_data.empty:
            for idx, row in dividend_data.iterrows():
                print(f"날짜: {idx.strftime('%Y-%m-%d')}, 배당금: ${row['dividend']:.4f}")
        else:
            print("배당금 데이터가 없습니다.")
        print("========================\n")
        
        chart_data = {
            'dates': stock_data.index.strftime('%Y-%m-%d').tolist(),
            'prices': stock_data['close'].tolist(),
            'volumes': stock_data['volume'].tolist(),
            'dividends': stock_data['dividend'].tolist(),
            'ticker': ticker,
            'start_date': start_date,
            'end_date': end_date
        }
        
        return jsonify(chart_data)
    except Exception as e:
        import traceback
        print('get-chart-data error:', traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/calculate-returns', methods=['POST'])
def api_calculate_returns():
    """투자 수익률을 계산합니다."""
    try:
        data = request.json
        ticker = data.get('ticker')
        investment_amount = float(data.get('investment_amount', 0))
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if not ticker or not start_date or investment_amount <= 0:
            return jsonify({'error': '잘못된 입력값입니다'}), 400
        
        # 수익률 계산
        results = calculate_returns(ticker, investment_amount, start_date, end_date)
        if results is None:
            return jsonify({'error': f'{ticker}의 수익률을 계산할 수 없습니다'}), 400
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/get-available-tickers', methods=['GET'])
def api_get_available_tickers():
    """사용 가능한 종목 목록을 반환합니다."""
    tickers = [
        {'value': 'TSLA', 'label': 'TSLA - Tesla Inc.'},
        {'value': 'TSLY', 'label': 'TSLY - Global X Autonomous & Electric Vehicles ETF'},
        {'value': 'KO', 'label': 'KO - Coca-Cola Company'},
        {'value': 'SCHD', 'label': 'SCHD - Schwab US Dividend Equity ETF'}
    ]
    return jsonify(tickers)

@main_bp.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    
    # Simple authentication for demo
    # TODO: Implement proper authentication
    if username == 'test' and password == 'test':
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token)
    
    return jsonify({'error': 'Invalid credentials'}), 401 