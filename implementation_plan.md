# DART 공시 연동 및 듀얼 볼린저 밴드 시스템 추가 계획서

사용자님의 요청에 따라, 기존 DART 공시 연동에 이어 **"듀얼 볼린저 밴드(Dual Bollinger Band) 단타 전략"**을 스캐너에 도입합니다.

## 🎯 주요 목표
1. **리스크 관리 극대화 (DART)**: 유상증자, 배임, 감자 등 치명적 악재를 공시 원문 제목을 통해 AI가 사전 차단합니다.
2. **가짜 반등(휩쏘) 필터링 (듀얼 볼린저 밴드)**: 장기 추세와 단기 모멘텀이 모두 일치하는 초강세 구간에서만 매수 타점을 잡도록 필터를 강화합니다.

---

## Proposed Changes

### 1. `utils/news_fetcher.py` [MODIFY]
*   `fetch_recent_notices(ticker)` 함수를 추가하여 DART 공시 제목 스크래핑.

### 2. `strategy/ai_agent.py` [MODIFY]
*   AI 프롬프트에 **[오늘의 최신 공시 내역]** 섹션 추가 및 악재 필터링 지시.

### 3. `strategy/ai_scorer.py` [MODIFY]
*   <span style="color: #ff9900;">**API 분봉 조회 수량 상향**: 120주기 이동평균선 계산을 위해 `limit`을 120개에서 200개로 변경.</span>
*   <span style="color: #ff9900;">**듀얼 볼린저 밴드 지표 추가**: `bb120_upper_1` (120일선 + 1표준편차), `bb20_upper_1` (20일선 + 1표준편차) 계산 추가.</span>
*   <span style="color: #ff9900;">**스코어링(타점) 고도화**:
    - **조건 1**: 주가가 `bb120_upper_1` 위에 있으면 +30점 (대세 상승 추세 탄탄함)
    - **조건 2**: 주가가 `bb20_upper_1`를 돌파하거나 그 위에 있으면 +20점 (단기 모멘텀 발생)</span>
