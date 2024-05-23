import os
import json
import click
import plexus
from jinja2 import Template

from plexus.logging import logging
from plexus.cli.console import console
from plexus.Registries import scorecard_registry

@click.group()
def report():
    """
    Generate reports for the scorecard.
    """
    pass

@click.option('--scorecard-name', required=True, help='The name of the scorecard to load data for')
@report.command()
def index(scorecard_name):
    """
    Generate an `index.html` at the root of the `reports/` folder with an HTML representation
    of the data in the reports.
    """

    plexus.Scorecard.load_and_register_scorecards('scorecards/')

    # First, find the scorecard class from the name.
    scorecard_class = scorecard_registry.get(scorecard_name)
    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return
    scorecard_id = scorecard_class.scorecard_id()

    scorecard_folder = os.path.join('.', 'scorecards', scorecard_name)
    scorecard_instance = scorecard_class(scorecard_folder_path=scorecard_folder)
    report_folder = os.path.join('.', 'reports', scorecard_instance.name())
    report_filename = os.path.join(report_folder, 'index.html')

    logging.info(f"Using scorecard key [purple][b]{scorecard_name}[/b][/purple] with class name [purple][b]{scorecard_instance.__class__.__name__}[/b][/purple]")
    logging.info(f"Generating [grey][b]{report_filename}[/b][/grey]")
    
    header_template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{{ scorecard.name() }} - Training Report</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400..900&display=swap" rel="stylesheet">
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400..900&family=Montserrat:ital,wght@0,100..900;1,100..900&display=swap" rel="stylesheet">
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Inconsolata:wght@200..900&display=swap" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
            <style>
            :root {
                --background: #ffffff;
                --focus-background: #F0F0F0;
                --neutral: #DDD;
                --red: #d33;
                --green: #393;
                --text: #333;
                --red-text: #d33;
                --green-text: #393;
            }
            h1, .cinzel-700 {
                font-family: "Cinzel", serif;
                font-optical-sizing: auto;
                font-weight: 700;
                font-style: normal;
                margin: 0;
            }
            h2 {
                margin-block-start: 0;
                margin-block-end: 0;
            }
            body, p, .montserrat {
                font-family: "Montserrat", sans-serif;
                font-optical-sizing: auto;
                font-weight: 400;
                font-style: normal;
            }
            .inconsolata, .fixed {
                font-family: "Inconsolata", monospace;
                font-optical-sizing: auto;
                font-weight: 700;
                font-style: bold;
            }
            body {
            margin: 2em 1em 1ex 1em;
            color: var(--text);
            background-color: var(--background);
            }
            header {
                display: block;
                margin: 0 0 1em 0;
                border: 1em solid var(--neutral);
                background-color: var(--neutral);
                border-radius: 1em;
            }
            header td {
                padding-right: 1ex;
            }
            header metadata {
                margin: 0;
            }
            section.session {
                padding: 0;
                border: 1em solid var(--focus-background);
                border-radius: 1em;
                margin: 0 -1em 1ex -1em;
                background-color: var(--focus-background);
            }
            .session + .session {
                margin-top: 3em;
            }
            section.session > metadata {
                display: block;
                border: 1em solid var(--neutral);
                border-radius: 1em;
                margin: 0 0 1em 0;
            }
            score {
                display: block;
                margin: 0;
                padding: 0;
                border: 1px solid var(--neutral);
                background-color: var(--neutral);
                border-radius: 1em;
                overflow: hidden;
            }
            score + score {
                margin-top: 1em;
            }
            score.correct {
                background-color: var(--green);
                border-color: var(--green);
            }
            score.incorrect {
                background-color: var(--red);
                border-color: var(--red)
            }
            metadata {
                display: block;
                margin: 1em;
                padding: calc(1em - 1px);
                border: 1px solid var(--neutral);
                color: var(--text);
                background-color: var(--background);
                border-radius: .7em;
            }
            element {
                display: block;
                margin: 1em 0 0 0;
                padding: calc(1em - 1px);
                border: 1px solid var(--neutral);
                color: var(--text);
                background-color: var(--background);
                border-radius: .7em;
            }
            .token_metrics {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 3em;
                width: 100%;
            }
            .metric {
                display: flex;
                justify-content: space-between;
            }
            .metric_name, .metric_value {
                display: block;
            }
            session.correct element {
                border-color: var(--green);
            }
            session.incorrect element {
                border-color: var(--red)
            }
            metadata, element {
                position: relative;
            }
            .correct {
                color: var(--green-text);
            }
            .incorrect {
                color: var(--red-text);
            }
            .label {
                font-weight: 700;
                letter-spacing: 0.12ex;
                padding: 1ex;
                border-radius: 1ex;
                color: var(--text);
                background-color: var(--neutral);
                text-align: center;
            }
            .label.correct {
                color: white;
                background-color: var(--green-text);
            }
            .label.incorrect {
                color: white;
                background-color: var(--red-text);
            }
            .collapsible_content {
                max-height: 0;
                overflow: hidden;
                transition: max-height 0.2s ease-out;
            }
            .collapsible_toggle:checked ~ .collapsible_content {
                max-height: unset;
            }
            .checkbox {
                display: inline-block;
            }
            .icon {
                position: absolute;
                top: 1em;
                right: 1em;
            }
            .fixed {
                font-family: "Inconsolata", monospace;
            }
            .json-data {
                font-family: "Inconsolata", monospace;
                font-weight: 700;
                font-style: bold;
                background-color: var(--focus-background);
                padding: 1em;
                border-radius: 0.5em;
                overflow-x: auto;
                white-space: pre;
            }
            footer {
                font-size: 0.8;
                text-align: center;
                margin-top: 2em;
            }
            .logotype {
                font-family: "Cinzel", serif;
                font-weight: 900;
                display: flex;
                justify-content: center;
            }
            .logotype a {
                color: #dc5497;
                text-decoration: none;
            }
            .logotype a .prominent {
                color: #0389d7;
            }
        </style>
        <script>
            function enlargeImage(base64Image) {
                // Create an overlay div
                var overlay = document.createElement("div");
                overlay.setAttribute("style", "position:fixed;top:0;left:0;width:100%;height:100%;background-color:rgba(0,0,0,0.85);z-index:1000;display:flex;justify-content:center;align-items:center;");
                overlay.addEventListener("click", function() {
                    document.body.removeChild(overlay);
                });

                // Create an img element
                var img = document.createElement("img");
                img.setAttribute("src", base64Image);
                img.setAttribute("style", "max-width:90%;max-height:90%;");

                // Append img to overlay, then overlay to body
                overlay.appendChild(img);
                document.body.appendChild(overlay);
            }
        </script>
    </head>
    <body>
        <header>
            <metadata>
                <h1>Training Report</h1>
                <p>{{ scorecard.name() }}</p>
            </metadata>
        </header>
    """)

    footer_template = Template("""
    </body>
    </html>
    """)

    score_template = Template("""
    <score class="{{ 'correct' if viable else '' }}">
    <metadata>
        <div style="display: flex; flex-direction: column; gap: 1em;">
            <div style="display: flex; justify-content: space-between; gap: 2em;">
                <div style="flex: 3; display: flex; flex-direction: column; gap: 1em;">
                    <div><h2>{{ score_name }}</h2></div>
                    {% if metrics %}
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); font-weight: bold; margin: 0 10%; gap: 3em;">
                        <div>Validation Accuracy</div>
                        <div>Validation F1 Score</div>
                        <div>Training Accuracy</div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 3em; margin: 0 10%;">
                        <div class="label">{{ '%.1f'|format(metrics['validation_accuracy']*100) }}</div>
                        <div class="label">{{ '%.1f'|format(metrics['validation_f1_score']*100) }}</div>
                        <div class="label">{{ '%.1f'|format(metrics['training_accuracy']*100) }}</div>
                    </div>
                    {% endif %}
                    <div><b>Configuration:</b></div>
                    <div class="collapsible_section">
                        <label for="collapsible">Click to expand</label>
                        <input type="checkbox" class="collapsible_toggle">
                        <div class="collapsible_content">
                            <pre class="json-data">{{ configuration | tojson(indent=4) }}</pre>
                        </div>
                    </div>

                    {% if data_profiling %}
                    <div><b>Data:</b></div>
                    <div class="collapsible_section">
                        <label for="collapsible">Click to expand</label>
                        <input type="checkbox" class="collapsible_toggle">
                        <div class="collapsible_content">
                            <pre class="json-data">{{ data_profiling | tojson(indent=4) }}</pre>
                        </div>
                    </div>
                    {% endif %}

                    {% if metrics %}
                    <div><b>Metrics:</b></div>
                    <div class="collapsible_section">
                        <label for="collapsible">Click to expand</label>
                        <input type="checkbox" class="collapsible_toggle">
                        <div class="collapsible_content">
                            <pre class="json-data">{{ metrics | tojson(indent=4) }}</pre>
                        </div>
                    </div>
                    {% endif %}

                    <div><b>Artifacts:</b></div>
                    <div class="collapsible_section">
                        <label for="collapsible">Click to expand</label>
                        <input type="checkbox" class="collapsible_toggle">
                        <div class="collapsible_content">
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1em;">
                                {% for artifact in artifacts %}
                                    <div style="display: flex; justify-content: center; align-items: start;">
                                        <img onclick="enlargeImage(this.src)" style="width: 100%; height: auto; max-width: 500px; margin-top: 2em;" src="{{ score_name }}/{{ artifact }}">
                                    </div>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </metadata>
    </score>
    """)

    report_html = header_template.render(scorecard=scorecard_instance)
    
    for score in scorecard_instance.scores.items():
        score_name = score[0]
        score_configuration = score[1]
        score_folder = os.path.join(report_folder, score_name)

        data_profiling_file_path = os.path.join(score_folder, 'data_profiling.json')
        if os.path.exists(data_profiling_file_path):
            with open(data_profiling_file_path) as data_profiling_file:
                data_profiling = json.load(data_profiling_file)
        else:
            data_profiling = None

        metrics_file_path = os.path.join(score_folder, 'metrics.json')
        if os.path.exists(metrics_file_path):
            with open(metrics_file_path) as metrics_file:
                metrics = json.load(metrics_file)
        else:
            metrics = None

        if os.path.exists(score_folder):
            artifacts = os.listdir(score_folder)
            artifacts = [f for f in artifacts if f not in ['configuration.json', 'metrics.json']]
        else:
            artifacts = []
        
        viable = False
        if metrics and metrics['validation_accuracy'] > 0.95:
            viable = True

        score_html = score_template.render(
            scorecard=scorecard_instance,
            score_name=score_name,
            configuration=score_configuration,
            data_profiling=data_profiling,
            metrics=metrics,
            artifacts=artifacts,
            viable=viable
        )
        report_html += score_html
        
    report_html += footer_template.render()
    
    with open(report_filename, 'w') as f:
        f.write(report_html)
