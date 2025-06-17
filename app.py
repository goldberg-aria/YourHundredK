import os
from app import create_app

# Flask 앱 생성
application = create_app()
app = application

if __name__ == '__main__':
    # 로컬 개발용
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 