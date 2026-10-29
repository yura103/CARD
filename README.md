# CardBenePICK

카드 혜택 추천과 소셜 정산을 체험하는 로컬 개발 MVP입니다. Python 3.12를 사용합니다.

## 실행

```bash
cd /workspace/CARD
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

브라우저에서 루트 경로를 열면 데모 화면이 표시됩니다. `/docs`는 API 문서, `/health`는 DB 접근을 포함한 상태 확인입니다. 인증 없는 데모이므로 공개 서비스로 배포하지 마세요. SQLite는 `data/card.db`에 저장되며 `CARD_DB`로 경로를 지정할 수 있습니다. 실제 개인정보를 입력하지 마세요.

## 현재 동작

- 한국어 카페·주유·편의점 키워드의 AND 검색과 전월 실적 상한 필터. 현재 화면은 규칙 기반 검색이며 LLM/RAG 응답이 아닙니다.
- 고정 데모 사용자의 보유 카드, 전월 실적, 월 잔여 한도로 예상 할인 계산. 모든 카드와 약관은 가상이며 조회는 한도를 소진하지 않습니다.
- 균등 정산, 원 단위 나머지의 본인 부담, SQLite 영속화, 중복 입금 확인 방지. 100만 원을 4명이 나누면 친구들 입금 75만 원을 상계하여 최종 본인 순지출은 25만 원입니다.
- FastAPI-MCP의 실제 Streamable HTTP `/mcp` 엔드포인트. 도구: `get_user_id`, `get_mcc_code`, `get_benefits_by_mcc`, `get_user_benefit_limit`, `get_sale`. 도구는 고정 데모 사용자만 조회하며 정산 변경 API는 MCP에 노출하지 않습니다. 매장명 매핑은 검증된 MCC가 아닙니다.

## 연동 준비 및 남은 작업

`app/search.py`는 Elasticsearch REST 기반 BM25 + kNN 검색, 혜택별 독립 Nested 필터, RRF와 필수 조건 재검증을 구현합니다. `infra/elasticsearch-mapping.json`으로 `cards` 인덱스를 준비하고 동일 모델로 생성한 384차원 문서/질문 임베딩을 전달해야 합니다. 현재 데모 화면에는 연결하지 않았으며 실제 ES 서버와 임베딩 모델 검증은 아직 수행하지 않았습니다. 한국어 분석기와 실제 카드 약관 수집·갱신도 필요합니다.

`dags/benefit_notifications.py`는 Airflow 3용 매일 한국시간 오전 8시 DAG입니다. Airflow worker에 프로젝트와 의존성을 설치하고 프로젝트 루트를 `PYTHONPATH`에 추가한 후 DAG를 등록하세요. 현재는 실적 알림 내용을 생성하는 preview 전용이며 실제 이메일/푸시를 보내지 않습니다. Airflow scheduler 실행 검증은 아직 수행하지 않았습니다. 생성 로직은 `python -m app.notifications`로 확인합니다.

LLM ReAct 실행기, 실제 로그인·사용자 격리, 마이데이터, GPS·지도 API, 카카오 공유, 송금 사업자 및 삼성페이 연동은 미구현입니다. 실제 송금 상계에는 인증된 사업자 웹훅, 서명 검증, 중복 이벤트 처리, 거래 대사가 필요합니다. 링크 방문만으로 입금 완료 처리해서는 안 됩니다.

## 검증

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m app.notifications
# 개발 서버 실행 중 별도 터미널에서 실제 MCP 도구 호출 검증:
.venv/bin/python scripts/smoke.py
```

핵심 계산·정산 API를 실제 ASGI 앱으로 검사합니다. Elasticsearch 어댑터 검사는 모의 HTTP를 사용하며 실제 서버 통합 검증과 구분합니다.

## 브랜치

기능 브랜치 → `dev` → `main` 순서로 PR을 만듭니다. 초기 MVP는 `dev`에서 통합 개발합니다. 외부 서비스 연동은 각 기능 브랜치를 최신 `dev`에서 갱신한 뒤 진행하세요.
