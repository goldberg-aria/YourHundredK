#!/usr/bin/env python3
"""
데이터베이스 초기화 스크립트
Render 배포 시 자동으로 테이블을 생성합니다.
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def init_database():
    """데이터베이스에 필요한 테이블들을 생성합니다."""
    
    # DATABASE_URL에서 연결 정보 가져오기
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("DATABASE_URL 환경변수가 설정되지 않았습니다.")
        return False
    
    try:
        # 데이터베이스 연결
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # schema.sql 파일 읽기
        with open('schema.sql', 'r') as f:
            schema_sql = f.read()
        
        # 테이블 생성 실행
        cur.execute(schema_sql)
        conn.commit()
        
        print("✅ 데이터베이스 테이블 생성 완료!")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ 데이터베이스 초기화 실패: {str(e)}")
        return False

if __name__ == '__main__':
    init_database() 