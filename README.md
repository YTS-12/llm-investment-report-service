# LLM 투자 보고서 생성 서비스

종목명을 넣으면 공시, 뉴스, 시세, 재무, 거시 지표를 모아서 LLM이 투자 분석 보고서를 써 주는 서비스다. FastAPI로 만들었고 로컬에서 돌리는 걸 전제로 한다.

국내 주식 하나 볼 때 DART 공시, 네이버 뉴스, 시세, 한국은행 거시지표를 매번 따로 찾아 정리하는 게 번거로웠다. 그걸 한 번에 묶어서 보고서 초안까지 만들어 보자는 생각으로 시작했다.

> 투자 자문이 아니라 공부 삼아 만든 도구다. LLM이 쓴 내용이라 틀릴 수 있으니 참고만 하고, 판단은 본인 몫이다.

## 무엇을 하나

- 종목명 입력 → 데이터 자동 수집 → 분석 보고서 생성
- 같은 종목을 다시 넣으면 이전 보고서와 비교해 바뀐 점 위주로 업데이트
- 두 종목 비교 보고서
- 보고서 맥락을 유지한 채로 이어서 후속 질문 (세션 단위)
- 생성한 보고서는 Meilisearch에 저장, 회사명으로 검색

## 동작 흐름

```
종목명 입력
  -> 회사명 정규화 / 종목코드 찾기
  -> 데이터 수집 (DART 공시, 네이버 뉴스, 네이버 증권 재무, Yahoo 시세, ECOS 거시)
  -> 정리 (공시 분류·중복제거·랭킹, 뉴스 중복제거, 재무 최신값 추출, 거시 해석)
  -> 기존 보고서 있으면 업데이트 / 없으면 신규 (라우터가 분기)
  -> LLM 체인: 사실 -> 분석 -> 리스크 -> 보고서 -> 구조화 출력
  -> Meilisearch 저장 + 화면 출력
```

수집한 다섯 종류(공시·뉴스·시세·재무·거시)는 우선순위 없이 같은 비중으로 LLM에 넘긴다. 처음엔 공시를 제일 위에 두는 식으로 가중치를 줬는데, 국면에 따라 오히려 한쪽으로 쏠리는 게 보여서 다 걷어내고 동등하게 두는 쪽으로 바꿨다.

## 기술 스택

- 백엔드: FastAPI + Uvicorn
- LLM: OpenAI gpt-4o-mini (LangChain으로 체인 구성, temperature 0.2)
- 워크플로: LangGraph (신규 / 업데이트 / 비교 / 라우터 그래프)
- 출력 형식: Pydantic 스키마 (`with_structured_output`)
- 저장/검색: Meilisearch, 세션 기억은 SQLite
- 수집/파싱: requests, BeautifulSoup, lxml, yfinance

## 데이터 출처

다섯 군데서 가져온다.

- OpenDART (`data_collectors/dart_api.py`, `normalize.py`): 정기·주요사항·거래소 공시 목록과 본문, 잠정실적 수치, 회사 corp_code와 종목코드. 실적, 증자, 계약, 지분변동, 자사주 같은 이벤트를 분류해서 쓴다.
- 네이버 증권 (`data_collectors/naver_finance_scraper.py`): 기업실적분석 표를 파싱해 매출·영업이익·순이익·ROE·부채비율 등의 최신 연간/분기 값, 그리고 현재가·시총·PER·PBR·목표주가 같은 지표.
- 네이버 뉴스 API (`data_collectors/naver_news_api.py`): 기사 제목, 요약, 링크, 날짜.
- Yahoo Finance (`data_collectors/yfinance_api.py`): 가격, 거래량.
- ECOS 한국은행 (`data_collectors/ecos_api.py`, `services/macro_interpretation_service.py`): 기준금리, 원/달러 환율, 선행·동행지수, 수출지수, 물가.

## 폴더 구조

```
app.py              FastAPI 진입점 (라우팅, 미들웨어, 예외 처리)
chains/             LLM 체인 (fact / analysis / risk / report / structured + update / compare / followup)
workflows/          LangGraph 워크플로 (report / update / compare / router)
services/           오케스트레이션, 데이터 파이프라인, 거시 해석, 메모리, 검색 등
data_collectors/    외부 데이터 수집 (dart / naver_finance / naver_news / yfinance / ecos / normalize)
indexing/           Meilisearch 클라이언트·스키마·인덱서
schemas/            Pydantic 출력 스키마
config/             sector_sensitivity.json (업종별 거시 민감도)
utils/              env 로딩, 로거, 재시도, 에러 핸들러
frontend/           정적 UI (index.html, styles.css, app.js)
tests/              pytest
evaluation/, batch/ 오프라인 품질 평가 / 일괄 생성 (웹 서비스 실행과는 무관)
```

## 실행 방법

필요한 건 Python 3.11 이상, 외부 API 키, 그리고 Meilisearch다. Meilisearch 실행 파일은 레포에 안 들어 있으니 [meilisearch.com](https://www.meilisearch.com/)에서 따로 받으면 된다.

설치:

```bash
git clone https://github.com/YTS-12/llm-investment-report-service.git
cd llm-investment-report-service

python -m venv .venv
.venv\Scripts\activate          # Windows. macOS/Linux는 source .venv/bin/activate
pip install -r requirements.txt
```

`.env.example`을 복사해서 `.env`를 만들고 본인 키를 채운다.

```env
OPENAI_API_KEY=...
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
ECOS_API_KEY=...
DART_API_KEY=...           # OPEN_DART_API_KEY에도 같은 값을 넣어 두면 편하다
OPEN_DART_API_KEY=...
MEILI_HOST=http://127.0.0.1:7700
MEILI_MASTER_KEY=local-meili-key
```

DART, ECOS, 네이버 검색 키는 무료로 발급받을 수 있고 OpenAI 키만 유료(사용량 과금)다. `.env`는 커밋하면 안 된다. `.env`와 로그, DB, `data.ms/`, Meilisearch 실행 파일은 `.gitignore`로 빼 뒀다.

실행은 터미널 두 개로 한다. 먼저 Meilisearch를 띄우고:

```bash
meilisearch --master-key local-meili-key    # .env의 MEILI_MASTER_KEY와 같은 값으로
```

다른 터미널에서 앱을 띄운다.

```bash
.\scripts\run_app.ps1        # http://127.0.0.1:8010
# 또는 직접:  uvicorn app:app --host 127.0.0.1 --port 8010
```

`http://127.0.0.1:8010/health`랑 `/config-status`를 열어서 `ready`가 true인지 보면 된다. false면 보통 `.env` 위치나 키 문제, 아니면 Meilisearch가 안 떠 있는 경우다.

## API

- `POST /generate-report`: 보고서 생성. body는 `session_id`, `company`, `sector`. 데이터를 직접 넣고 싶으면 `news`/`disclosures`/`market_data`/`macro`도 같이 보낼 수 있다(안 보내면 자동 수집).
- `POST /compare-report`: 두 종목 비교. `company_a`, `sector_a`, `company_b`, `sector_b`.
- `POST /chat-followup`: 후속 질문. `session_id`, `company`, `question`.
- `GET /reports?company=...`: 저장된 보고서 검색.
- `GET /memory/{session_id}`: 세션 대화 기록.
- `GET /health`, `GET /config-status`: 상태 확인.

## 테스트

```bash
pytest
```

`tests/`는 외부 API 없이 도는 로직 위주로 짰다. 공시 파싱·분류(`test_dart_parsing`), 네이버 재무표 최신값 추출(`test_naver_finance`), 공시 랭킹·중복제거(`test_pipeline_logic`), 거시 해석(`test_services_logic`), 재시도(`test_retry`), 종목코드 해석(`test_ticker_resolution`), 세션 메모리(`test_memory_service`).

## 구현하면서 신경 쓴 것들

- 공시를 그냥 최신순으로 받으면 삼성전자처럼 지분공시가 쏟아지는 종목은 실적 공시가 뒤로 밀려서 안 잡힌다. 그래서 공시 유형(A 정기 / B 주요사항 / I 거래소)으로 나눠 받아서 합친다.
- 정정본과 원본 잠정실적이 단위만 다르게(조 단위 vs 억 단위) 중복으로 들어오면 LLM이 "수치가 안 맞는다"고 헷갈려해서, 단위 깔끔한 한 건만 남기도록 했다.
- 네이버 재무표에서 추정치(E) 칸을 빼고 실제 실적 최신값을 뽑는다. 예전엔 그냥 앞에서 몇 개 집어서 두 해 전 값이 잡히는 버그가 있었다.
- 업종별 금리/환율/경기/물가 민감도는 `config/sector_sensitivity.json`에 점수로 빼 놨다. 논문이랑 리서치(KRX 패널 연구, FDIC, Fidelity/MSCI 등) 보고 방향과 강도를 정했고, 근거가 약한 업종은 값을 보수적으로 잡았다.
- 외부 호출은 재시도로 한 번 감싸고(`utils/retry.py`), LLM 생성이 실패하면 수집한 입력만으로 폴백 보고서라도 내보낸다.

## 알려진 한계

- 네이버 증권은 페이지 스크래핑이고 야후는 비공식 API라, 저쪽 구조가 바뀌면 해당 수집이 깨질 수 있다. 그래도 한 곳이 실패한다고 전체가 멈추진 않게 했다.
- 보고서 생성에는 OpenAI 키(유료)가 있어야 한다.
- 로컬 실행만 염두에 두고 만들었고, 배포용 설정은 따로 없다.
