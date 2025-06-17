import os
from app import create_app

# Flask 애플리케이션 생성
application = create_app()

if __name__ == '__main__':
    application.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 