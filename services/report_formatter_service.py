def _normalize_text(value: str, fallback: str = "정보 없음") -> str:
    text = (value or "").strip()
    return text if text else fallback


def _to_bullets(value: str) -> str:
    text = _normalize_text(value)
    if text == "정보 없음":
        return "- 정보 없음"

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "- 정보 없음"

    formatted = []
    for line in lines[:8]:
        formatted.append(line if line.startswith("- ") else f"- {line}")
    return "\n".join(formatted)


def build_fallback_report(
    company: str,
    news: str = "",
    disclosures: str = "",
    market_data: str = "",
    macro: str = "",
    reason: str = "",
) -> str:
    reason_text = _normalize_text(
        reason,
        "LLM 응답을 받지 못해 입력 데이터 기반의 fallback 보고서를 생성했습니다.",
    )

    return f"""# {company} 투자 보고서

## 투자 판단 요약
- 현재 결과는 fallback 경로에서 생성되었습니다.
- 입력 데이터의 핵심 포인트를 우선 정리해 빠른 점검에 초점을 맞췄습니다.
- 보다 정교한 판단을 위해서는 LLM 기반 구조화 생성 결과를 함께 확인하는 것이 좋습니다.

## 기업 개요
{company}에 대한 자동 생성 보고서입니다. 현재는 입력된 데이터와 구조화된 공시 요약을 기반으로 핵심 포인트를 정리했습니다.

## 최근 핵심 포인트
### 뉴스
{_to_bullets(news)}

### 공시
{_to_bullets(disclosures)}

### 시장 데이터
{_to_bullets(market_data)}

### 거시환경 영향
{_to_bullets(macro)}

## 공시/이벤트 해설
구조화된 공시 요약에 포함된 계약 규모, 자금조달 목적, 지분 변동, 주주환원 수치부터 우선 확인하는 것이 좋습니다.

{_normalize_text(disclosures)}

## 핵심 리스크
- 현재 보고서는 fallback 경로에서 생성되어 정교한 LLM 해석이 제한될 수 있습니다.
- 입력 데이터가 부족하거나 최신성이 떨어지면 해석 정확도가 낮아질 수 있습니다.
- 공시와 시장 데이터의 원문을 함께 확인하면 판단의 신뢰도를 높일 수 있습니다.

## 종합 판단
현재 결과는 비상 fallback 보고서입니다. 다만 구조화된 공시 데이터와 시장 데이터가 포함되어 있어 주요 투자 포인트를 빠르게 점검하는 용도로는 유효합니다.

## 관찰 포인트 체크리스트
- 공시의 후속 정정 여부
- 수주/자금조달 이벤트의 실제 실적 반영 여부
- 지분변동 및 주주환원 정책의 지속 여부

## 10줄 요약
- fallback 보고서가 생성되었습니다.
- 뉴스, 공시, 시장 데이터, 거시 입력이 요약되었습니다.
- 공시 세부 수치가 우선 반영되었습니다.
- 수주/조달/지분변동 이벤트를 먼저 확인해야 합니다.
- 최신 공시 정정 여부를 체크해야 합니다.
- 실적 발표 일정과 후속 공시를 확인해야 합니다.
- 가격 및 수급 흐름을 함께 점검해야 합니다.
- 거시 환경 변화도 업종 영향과 함께 봐야 합니다.
- 입력 데이터 품질이 높을수록 보고서 신뢰도가 높아집니다.
- fallback_reason: {reason_text}
"""


def build_fallback_compare_report(
    company_a: str,
    company_b: str,
    report_a: str = "",
    report_b: str = "",
    reason: str = "",
) -> str:
    return f"""# {company_a} vs {company_b} 비교 보고서

## 비교 요약
현재는 비교 체인 실행이 원활하지 않아 각 종목의 최신 보고서를 기반으로 비교 초안을 생성했습니다.

## {company_a}
{_normalize_text(report_a)}

## {company_b}
{_normalize_text(report_b)}

## 비교 관찰 포인트
- 공시 이벤트 강도 차이
- 계약/조달/지분변동의 방향 차이
- 시장 데이터와 거시 민감도의 차이

## 생성 상태
- fallback_reason: {_normalize_text(reason, '비교 체인 실행 실패')}
"""


def build_fallback_followup_answer(
    question: str,
    latest_report: str = "",
    reason: str = "",
) -> str:
    latest = _normalize_text(latest_report, "이전 보고서 없음")
    return (
        f"질문: {question}\n\n"
        "현재는 후속 질문에 대한 LLM 응답을 직접 생성하지 못했습니다. "
        "대신 최신 보고서를 다시 참고할 수 있도록 요약을 제공합니다.\n\n"
        f"[최신 보고서 요약]\n{latest}\n\n"
        f"[fallback_reason]\n{_normalize_text(reason, '후속 질문 체인 실행 실패')}"
    )
