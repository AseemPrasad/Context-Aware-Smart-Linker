"""Evaluation metrics reporting and dashboard generation.

Produces JSON, HTML, and CSV reports for evaluation results.
Includes trend analysis and breakdown by category.
"""

import os
import json
import csv
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MetricsReport:
    """Aggregated metrics report."""

    run_id: str
    timestamp: str
    dataset_name: str
    sample_size: int
    faithfulness: float
    relevance: float
    precision: float
    pass_rate: float
    runtime_seconds: float


class MetricsReporter:
    """Generate evaluation metrics reports in multiple formats."""

    def __init__(self, results_dir: str = "evals/results"):
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)

    def generate_json_report(self, summary: Dict[str, Any], run_id: str) -> str:
        """Generate JSON report of evaluation results.

        Args:
            summary: Summary dict from evaluation
            run_id: Unique run identifier

        Returns:
            Path to saved JSON report
        """
        report_path = os.path.join(self.results_dir, f"{run_id}_report.json")

        report = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "summary": summary,
            "thresholds": {
                "faithfulness_min": 0.85,
                "relevance_min": 0.80,
                "precision_min": 0.75,
            },
        }

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"JSON report saved: {report_path}")
        return report_path

    def generate_html_report(self, summary: Dict[str, Any], run_id: str) -> str:
        """Generate HTML report with visualizations.

        Args:
            summary: Summary dict from evaluation
            run_id: Unique run identifier

        Returns:
            Path to saved HTML report
        """
        report_path = os.path.join(self.results_dir, f"{run_id}_report.html")

        html_content = f"""
        <html>
        <head>
            <title>Evaluation Report - {run_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .header {{ background: #333; color: white; padding: 20px; border-radius: 5px; }}
                .metric-card {{ background: white; padding: 15px; margin: 10px 0; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric-label {{ font-weight: bold; color: #333; }}
                .metric-value {{ font-size: 24px; color: #007bff; margin: 10px 0; }}
                .status-pass {{ color: #28a745; font-weight: bold; }}
                .status-fail {{ color: #dc3545; font-weight: bold; }}
                .progress-bar {{ width: 100%; height: 20px; background: #e9ecef; border-radius: 3px; overflow: hidden; }}
                .progress-fill {{ height: 100%; background: #007bff; transition: width 0.3s; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background: white; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #f8f9fa; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Evaluation Report</h1>
                <p>Run ID: {run_id}</p>
                <p>Timestamp: {datetime.utcnow().isoformat()}</p>
            </div>

            <div class="metric-card">
                <div class="metric-label">Pass Rate</div>
                <div class="metric-value {('status-pass' if summary.get('pass_rate', 0) >= 0.8 else 'status-fail')}">
                    {summary.get('pass_rate', 0):.1%}
                </div>
            </div>

            <div class="metric-card">
                <div class="metric-label">Faithfulness Score</div>
                <div class="metric-value">{summary.get('mean_faithfulness', 0):.2f}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {summary.get('mean_faithfulness', 0) * 100}%"></div>
                </div>
                <p>Target: ≥ 0.85</p>
            </div>

            <div class="metric-card">
                <div class="metric-label">Answer Relevance Score</div>
                <div class="metric-value">{summary.get('mean_relevance', 0):.2f}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {summary.get('mean_relevance', 0) * 100}%"></div>
                </div>
                <p>Target: ≥ 0.80</p>
            </div>

            <div class="metric-card">
                <div class="metric-label">Context Precision Score</div>
                <div class="metric-value">{summary.get('mean_precision', 0):.2f}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {summary.get('mean_precision', 0) * 100}%"></div>
                </div>
                <p>Target: ≥ 0.75</p>
            </div>

            <div class="metric-card">
                <div class="metric-label">Results Summary</div>
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Status</th>
                    </tr>
                    <tr>
                        <td>Total Questions Evaluated</td>
                        <td>{summary.get('total_questions', 0)}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>Passed</td>
                        <td>{summary.get('passed', 0)}</td>
                        <td class="status-pass">✓</td>
                    </tr>
                    <tr>
                        <td>Failed</td>
                        <td>{summary.get('failed', 0)}</td>
                        <td class="status-fail">✗</td>
                    </tr>
                    <tr>
                        <td>Dataset</td>
                        <td>{summary.get('dataset_name', 'N/A')}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>Runtime</td>
                        <td>{summary.get('runtime_seconds', 0):.1f}s</td>
                        <td>-</td>
                    </tr>
                </table>
            </div>
        </body>
        </html>
        """

        with open(report_path, "w") as f:
            f.write(html_content)

        logger.info(f"HTML report saved: {report_path}")
        return report_path

    def append_to_csv(self, summary: Dict[str, Any], run_id: str) -> str:
        """Append evaluation metrics to CSV history file.

        Args:
            summary: Summary dict from evaluation
            run_id: Unique run identifier

        Returns:
            Path to CSV file
        """
        csv_path = os.path.join(self.results_dir, "metrics_history.csv")

        row = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "dataset": summary.get("dataset_name", ""),
            "total_questions": summary.get("total_questions", 0),
            "passed": summary.get("passed", 0),
            "pass_rate": summary.get("pass_rate", 0),
            "faithfulness": summary.get("mean_faithfulness", 0),
            "relevance": summary.get("mean_relevance", 0),
            "precision": summary.get("mean_precision", 0),
            "runtime_seconds": summary.get("runtime_seconds", 0),
        }

        # Check if file exists (to add header only on first write)
        file_exists = os.path.exists(csv_path)

        with open(csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        logger.info(f"Metrics appended to CSV: {csv_path}")
        return csv_path

    def get_trend_analysis(self, num_runs: int = 10) -> Dict[str, Any]:
        """Analyze recent evaluation trend.

        Args:
            num_runs: Number of recent runs to analyze

        Returns:
            Trend analysis dict
        """
        csv_path = os.path.join(self.results_dir, "metrics_history.csv")

        if not os.path.exists(csv_path):
            return {"message": "No evaluation history available"}

        try:
            with open(csv_path, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                return {"message": "No evaluation data in history"}

            recent = rows[-num_runs:]
            scores = [float(row.get("faithfulness", 0)) for row in recent]

            mean_score = sum(scores) / len(scores) if scores else 0
            min_score = min(scores) if scores else 0
            max_score = max(scores) if scores else 0

            # Calculate trend
            if len(scores) >= 2:
                trend = scores[-1] - scores[0]
                trend_direction = "↑" if trend > 0 else ("↓" if trend < 0 else "→")
            else:
                trend = 0
                trend_direction = "→"

            return {
                "num_runs_analyzed": len(recent),
                "mean_faithfulness": round(mean_score, 4),
                "min_faithfulness": round(min_score, 4),
                "max_faithfulness": round(max_score, 4),
                "trend": round(trend, 4),
                "trend_direction": trend_direction,
            }

        except Exception as e:
            logger.error(f"Error analyzing trend: {e}")
            return {"error": str(e)}


def get_reporter(results_dir: str = "evals/results") -> MetricsReporter:
    """Get singleton metrics reporter instance."""
    return MetricsReporter(results_dir)
