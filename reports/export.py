import json
from dataclasses import asdict

from reports.publish import SignedReport


def report_to_data(report: SignedReport) -> dict:
    return {
        'report_id': report.report_id,
        'left_only': None if report.left_only is None else list(report.left_only),
        'right_only': None if report.right_only is None else list(report.right_only),
        'parents': [asdict(parent) for parent in report.parents],
        'receipt': asdict(report.receipt),
    }


def export_report(report: SignedReport) -> str:
    return json.dumps(report_to_data(report), ensure_ascii=False, sort_keys=True)
