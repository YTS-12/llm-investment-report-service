import json
from pathlib import Path

from services.report_service import generate_investment_report
from services.report_store_service import save_report_to_index

WATCHLIST_PATH = Path(__file__).resolve().parent / "watchlist.json"

def run_batch():
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        watchlist = json.load(f)

    for idx, item in enumerate(watchlist):
        session_id = f"batch_{idx}"

        result = generate_investment_report(
            company=item["company"],
            news=item["news"],
            disclosures=item["disclosures"],
            market_data=item["market_data"],
            macro=item["macro"],
        )

        save_report_to_index(session_id, result)
        print(f"{item['company']} 보고서 생성 및 저장 완료")

if __name__ == "__main__":
    run_batch()
