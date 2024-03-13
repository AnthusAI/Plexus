from jinja2 import Environment, PackageLoader, select_autoescape
import csv

class ScorecardReport:
    def __init__(self, results, metrics):
        self.results = results
        self.metrics = metrics
        self.env = Environment(
            loader=PackageLoader('scorecard_scores', 'templates'),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def generate_html_report(self):
        template = self.env.get_template('scorecard_report.html')
        report = template.render(results=self.results, metrics=self.metrics)
        return report

    def generate_csv_report(self):
        report = "session_id,question_name,human_label,result_value,correct_value\n"
        for result in self.results:
            report += f"{result['session_id']}, {result['question_name']}, {result['human_label']}, {result['result'].value}, ,\n"
        return report