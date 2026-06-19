INDEX_CONFIG = {
    "stocks": {
        "primary_key": "doc_id",
        "filterable_attributes": ["market", "sector", "industry", "country"],
        "searchable_attributes": ["symbol", "name", "sector", "industry", "summary"],
    },
    "news": {
        "primary_key": "doc_id",
        "filterable_attributes": ["ticker", "stock_name", "source"],
        "searchable_attributes": ["title", "summary", "stock_name", "ticker"],
    },
    "disclosures": {
        "primary_key": "doc_id",
        "filterable_attributes": ["corp_name", "source", "receipt_date"],
        "searchable_attributes": ["corp_name", "report_name", "flr_name"],
    },
    "reports": {
        "primary_key": "doc_id",
        "filterable_attributes": ["company", "session_id", "report_mode", "judgement"],
        "searchable_attributes": [
            "company",
            "one_line_summary",
            "investment_thesis",
            "fact_summary",
            "analysis_summary",
            "risk_summary",
            "final_report",
        ],
    },
}
