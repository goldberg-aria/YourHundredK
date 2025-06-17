-- 주식 가격 테이블
CREATE TABLE IF NOT EXISTS stocks (
    ticker VARCHAR(10),
    date DATE,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume BIGINT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, date)
);

-- 배당금 테이블
CREATE TABLE IF NOT EXISTS dividends (
    ticker VARCHAR(10),
    date DATE,
    amount FLOAT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, date)
);

-- 주식 분할/병합 테이블
CREATE TABLE IF NOT EXISTS splits (
    ticker VARCHAR(10),
    date DATE,
    ratio FLOAT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, date)
);

-- 사용자 테이블 (향후 확장용)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 구매 내역 테이블 (향후 확장용)
CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    amount FLOAT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
); 