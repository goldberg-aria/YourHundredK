from flask import Blueprint, jsonify, request, render_template
from flask_jwt_extended import jwt_required, create_access_token
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime
from .stock_data import fetch_stock_data, calculate_returns, get_stock_data

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
            return jsonify({'error': 'Invalid input parameters'}), 400
        
        # 수익률 계산
        results = calculate_returns(ticker, investment_amount, start_date, end_date)
        if results is None:
            return jsonify({'error': f'Failed to calculate returns for {ticker}'}), 400
        
        # 차트 데이터 가져오기
        stock_data = get_stock_data(ticker, start_date, end_date)
        if stock_data.empty:
            return jsonify({'error': f'No data available for {ticker}'}), 400
        
        # Plotly 차트 생성
        fig = go.Figure(data=[
            go.Scatter(
                x=stock_data['date'],
                y=stock_data['close_price'],
                mode='lines',
                name='Stock Price'
            )
        ])
        
        # 배당금 표시
        dividend_data = stock_data[stock_data['dividend'] > 0]
        if not dividend_data.empty:
            fig.add_trace(
                go.Scatter(
                    x=dividend_data['date'],
                    y=dividend_data['close_price'],
                    mode='markers',
                    name='Dividend',
                    marker=dict(
                        symbol='star',
                        size=10,
                        color='green'
                    )
                )
            )
        
        # 차트 레이아웃 업데이트
        period_str = f"{results['start_date']} to {results['end_date']}"
        fig.update_layout(
            title=f'{ticker} Price History and Dividends ({period_str})',
            xaxis_title='Date',
            yaxis_title='Price ($)',
            hovermode='x unified'
        )
        
        # 결과에 차트 추가
        results['chart'] = pio.to_html(fig, full_html=False)
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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