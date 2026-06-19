import json
from pathlib import Path

from services.report_service import generate_investment_report
from evaluation.quality_checks import contains_required_sections, contains_keywords

DATASET_PATH = Path(__file__).resolve().parent / "eval_dataset.json"

def run_local_eval():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    all_results = []

    for sample in dataset:
        result = generate_investment_report(
            company=sample["company"],
            news=sample["news"],
            disclosures=sample["disclosures"],
            market_data=sample["market_data"],
            macro=sample["macro"],
        )

        report_text = result["final_report"]

        section_check = contains_required_sections(report_text)
        keyword_check = contains_keywords(report_text, sample["expected_keywords"])

        all_results.append({
            "company": sample["company"],
            "sections": section_check,
            "keywords": keyword_check,
            "report_preview": report_text[:300]
        })

    return all_results


if __name__ == "__main__":
    results = run_local_eval()
    for r in results:
        print("=" * 100)
        print(r)
