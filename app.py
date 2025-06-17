import os
from app import create_app

# 환경 변수에서 설정 가져오기
config_name = os.getenv('FLASK_ENV', 'production')

# Flask 앱 생성
app = create_app()

if __name__ == '__main__':
    # 로컬 개발용
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 