# Cache Clear File

Update timestamp: 2025-06-18 03:30:00 KST

Recent Changes:
- Fixed dividend data matching logic for monthly dividend ETFs like TSLY
- Improved month-end calculation for accurate dividend period matching
- Added dividend debugging information to show actual dividend counts
- Enhanced timezone handling for dividend data filtering
- Fixed monthly dividend recognition (TSLY should show 12+ dividends, not 5)

Purpose: Force Streamlit Cloud cache clear and redeploy

Key fixes for dividend matching:
1. Proper monthly period calculation for dividend filtering
2. Enhanced dividend data timezone conversion
3. Added debugging info to verify dividend data count
4. Fixed monthly dividend ETF support (TSLY, NVDY, CONY etc)
5. Improved dividend-to-month matching algorithm

Note: TSLY has 31 dividend records and should show 12+ monthly dividends in simulation, not just 5.

## 변경사항
- 수익률 계산 로직 수정
- 타임존 처리 개선  
- 배당금 계산 방식 개선
- 통합 수익률 추가

## 목표
- 비현실적인 수익률 (700%+) 문제 해결
- 그록 계산과 일치하는 현실적인 수익률 달성 