import json
from pathlib import Path

from services.report_service import generate_investment_report
from evaluation.report_quality_score import (
    score_required_sections,
    score_expected_keywords,
    overall_quality_score,
)

DATASET_PATH = Path(__file__).resolve().parent / "expanded_eval_dataset.json"


def run_eval_v2():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    results = []

    for sample in dataset:
        result = generate_investment_report(
            company=sample["company"],
            news=sample["news"],
            disclosures=sample["disclosures"],
            market_data=sample["market_data"],
            macro=sample["macro"],
        )

        report_text = result.get("final_report", "")

        sec_result = score_required_sections(report_text, sample["expected_sections"])
        kw_result = score_expected_keywords(report_text, sample["expected_keywords"])

        total_score = overall_quality_score(sec_result["score"], kw_result["score"])

        results.append({
            "company": sample["company"],
            "section_score": sec_result,
            "keyword_score": kw_result,
            "overall_score": total_score,
            "report_preview": report_text[:500],
        })

    return results
