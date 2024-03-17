import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
import seaborn as sns
from graphviz import Digraph
from jinja2 import Environment, PackageLoader, select_autoescape
import csv
import base64
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import mlflow

from plexus.CustomLogging import logging
from plexus.CompositeScore import CompositeScore

class ScorecardResultsAnalysis:
    def __init__(self, *, scorecard_results):
        self.scorecard_results = scorecard_results

    def _extract_score_names(self):
        # Implement logic to extract score names from scorecard_results
        # This is a placeholder implementation
        return list(self.scorecard_results.data[0]['results'].keys())

    def calculate_overall_accuracy(self):
        total_correct_scores = 0
        total_scores = 0
        for entry in self.scorecard_results.data:
            for score_detail in entry['results'].values():
                total_scores += 1
                if score_detail.get('correct', False):
                    total_correct_scores += 1
        overall_accuracy_percentage = (total_correct_scores / total_scores * 100) if total_scores else 0
        return {
            'total_correct_scores': total_correct_scores,
            'total_scores': total_scores,
            'overall_accuracy_percentage': overall_accuracy_percentage
        }

    def calculate_total_cost(self, mode=None):
        total_cost = 0
        for scorecard_result in self.scorecard_results.data:
            for score_result in scorecard_result.get('results', {}).values():
                for element_result in score_result.get('element_results', []):
                    # try:
                        element_metadata = element_result.metadata
                        if mode == 'production' and element_metadata.get('element_name') == 'summary':
                            continue
                        total_cost += element_metadata.get('total_cost', 0)
                    # except KeyError:
                        # pass
        return total_cost

    def calculate_row_accuracy(self, entry):
        total_correct_scores = 0
        total_scores = 0
        for score_detail in entry['results'].values():
            total_scores += 1
            if score_detail.get('correct', False):
                total_correct_scores += 1
        row_accuracy_percentage = (total_correct_scores / total_scores * 100) if total_scores else 0
        return row_accuracy_percentage

    def plot_accuracy_heatmap(self):

        def _prepare_heatmap_data(self):
            heatmap_data = []
            annotations = []
            for result in self.scorecard_results.data:
                data_row = []
                annotation_row = []
                for question in self._extract_score_names():
                    score_label = str(result['results'][question].get('value', 'NA')).lower()
                    human_label = str(result['results'][question].get('human_label', 'NA')).lower()
                    logging.info(f"Question: {question}, score Label: {score_label}, Human Label: {human_label}")
                    data_row.append(result['results'][question].get('correct', False))  # Use 1 for match, 0 for mismatch for the heatmap
                    annotation_row.append(f"{score_label}\nh:{human_label}")
                heatmap_data.append(data_row)
                annotations.append(annotation_row)
            return heatmap_data, annotations

        # Assuming self.evaluation_results is already populated with accuracy data
        # Extract heatmap data and annotations from evaluation_results
        heatmap_data, annotations = _prepare_heatmap_data(self)

        # Convert the list of rows into a DataFrame
        score_names = self._extract_score_names()  # Assuming this method is implemented
        heatmap_df = pd.DataFrame(heatmap_data, columns=score_names)

        if heatmap_df.empty:
            raise ValueError("The heatmap DataFrame is empty. Please check the data.")

        cmap = ListedColormap(['red', 'green'])
        vmin, vmax = 0, 1
        heatmap_width = max(len(heatmap_df.columns) * 1, 10)
        heatmap_height = max(len(heatmap_df) * 1, 4)

        fig, ax = plt.subplots(figsize=(heatmap_width, heatmap_height))
        sns.heatmap(heatmap_df, annot=np.array(annotations), fmt='', cmap=cmap, linewidths=.5, cbar=False, ax=ax, vmin=vmin, vmax=vmax)

        overall_accuracy = self.calculate_overall_accuracy()['overall_accuracy_percentage']
        ax.set_title('Accuracy Compared With Human Labels', fontsize=16)
        ax.set_xlabel(f"Overall Accuracy: {overall_accuracy:.2f}%", fontsize=14)

        row_accuracies = [self.calculate_row_accuracy(result) for result in self.scorecard_results.data]

        # Convert the list of rows into a DataFrame
        score_names = self._extract_score_names()
        heatmap_df = pd.DataFrame(heatmap_data, columns=score_names)

        # Plotting code...
        for i, (result, row_accuracy) in enumerate(zip(self.scorecard_results.data, row_accuracies)):
            transcript_id = result['session_id'][:5]
            ax.text(-0.4, i + 0.5, transcript_id, va='center', ha='right', transform=ax.transData, fontsize=14)
            ax.text(len(heatmap_df.columns) + 0.1, i + 0.5, f"{row_accuracy:.2f}%", va='center', ha='left', transform=ax.transData, fontsize=14, family='monospace')

        plt.tight_layout()
        plt.savefig('mlruns/accuracy_heatmap.png', bbox_inches='tight', pad_inches=0.2)

    def generate_html_report(self, *, only_incorrect_scores=False, redact_cost_information=False,
            title="Scorecard Report",
            subtitle="This report contains the results of scorecard evaluations, with detailed reasoning and explanations for each score."
        ):

        # We need to compute a `results` list containing the ScoreResult for each score,
        # as a long, flat list, over all scorecard results.
        results = []
        visualization_tasks = []
        with ThreadPoolExecutor() as executor:
            for scorecard_result in self.scorecard_results.data:
                for score_result in scorecard_result['results']:    

                    # Add the session ID to it.
                    scorecard_result['results'][score_result]['session_id'] = \
                        scorecard_result['session_id']

                    if scorecard_result['results'][score_result]['error'] is None:
                        task = executor.submit(
                            self.visualize_decision_path,
                            score_result=scorecard_result['results'][score_result],
                            decision_tree=scorecard_result['results'][score_result]['decision_tree'],
                            element_results=scorecard_result['results'][score_result]['element_results'],
                            session_id=scorecard_result['session_id'],
                            score_name=score_result
                        )
                        visualization_tasks.append((task, scorecard_result, score_result))

            # Process completed tasks
            for future, scorecard_result, score_result in visualization_tasks:
                visualization_image_path = future.result()
                # Encode the image as base64
                with open(visualization_image_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
                # Embed the base64-encoded image in the HTML
                scorecard_result['results'][score_result]['visualization_image_base64'] = encoded_string

                # Add this one to the list if it meets the criteria
                if not (only_incorrect_scores and scorecard_result['results'][score_result]['correct']):
                    results.append(scorecard_result['results'][score_result])

        # Extra metadata at the overall experiment level.
        metrics = {
            'overall_accuracy': {
                'label': 'Overall Accuracy',
                'value': f"{self.calculate_overall_accuracy()['overall_accuracy_percentage']:.2f}%"
            }
        }
        if not redact_cost_information:
            total_cost = self.calculate_total_cost()
            number_of_transcripts = len(self.scorecard_results.data)
            cost_per_transcript = total_cost / number_of_transcripts

            total_production_cost = self.calculate_total_cost(mode='production')
            production_cost_per_transcript = total_production_cost / number_of_transcripts

            metrics.update({
                'total_cost': {
                    'label': 'Total Cost',
                    'value': f"${total_cost:.2f}"
                },
                'cost_per_transcript': {
                    'label': 'Cost Per Transcript',
                    'value': f"${cost_per_transcript:.2f}"
                },
                'total_production_cost': {
                    'label': 'Total Production Cost',
                    'value': f"${total_production_cost:.2f}"
                },
                'production_cost_per_transcript': {
                    'label': 'Production Cost Per Transcript',
                    'value': f"${production_cost_per_transcript:.2f}"
                }
            })

        # Use Jinja2 to generate the HTML report.
        self.env = Environment(
            loader=PackageLoader('plexus', 'templates')
        )
        template = self.env.get_template('scorecard_report.html')
        report = template.render(
            results=results,
            metrics=metrics,
            title=title,
            subtitle=subtitle,
            only_incorrect_scores=only_incorrect_scores,
            redact_cost_information=redact_cost_information,
        )

        return report

    def visualize_decision_path(self, *, score_result, decision_tree, element_results, session_id, score_name, filename=None):

        if filename is None:
            filename = f'/tmp/decision_path_visualization_{session_id}_{CompositeScore.normalize_element_name(score_name)}.png'

        # Define the outcome nodes with unique IDs at the beginning of the method
        outcome_nodes = {
            'yes': 'node_yes',
            'no': 'node_no',
            'na': 'node_na'
        }

        logging.debug(f"Score result: {score_result['value']}")

        if decision_tree is None:
            logging.error("Decision tree is not provided. Aborting visualization.")
            return

        logging.debug("Elements results:")
        for element in element_results:
            logging.debug(f"  {element.metadata['element_name']}: {element.value}")

        # Initialize the dictionary to keep track of created nodes and their IDs
        created_nodes = {}

        dot = Digraph(comment='Decision Path Visualization')
        dot.attr(rankdir='TB')
        dot.attr('node', style='filled, rounded', shape='box', fontname='Helvetica-Bold', fontsize='14')
        dot.attr('edge', fontname='Helvetica-Bold', fontsize='14')
        dot.graph_attr['dpi'] = '300'

        # Default colors for outcome nodes
        outcome_colors = {
            'yes': '#666666',
            'no': '#666666',
            'na': '#666666'
        }

        # Update the color of the correct outcome node based on the score_result
        final_outcome = score_result['value'].lower()
        if final_outcome in outcome_colors:
            if final_outcome == 'yes':
                outcome_colors[final_outcome] = '#339933'  # Green
            elif final_outcome == 'no':
                outcome_colors[final_outcome] = '#DD3333'  # Red
            elif final_outcome == 'na':
                outcome_colors[final_outcome] = '#000000'  # Black

        # Create the outcome nodes with the determined colors
        dot.attr(rankdir='TB')
        with dot.subgraph() as s:
            s.attr(rank='sink')
            # Create the outcome nodes within this subgraph
            for outcome, color in outcome_colors.items():
                s.node(outcome_nodes[outcome], outcome.upper(), color=color, fontcolor='white')

        def did_element_decision_happen(element_name, element_results):
            return any(result.metadata['element_name'] == element_name for result in element_results)

        def was_element_positive(element_name, element_results):
            # Check if any result for the element is 'Yes'
            return any(result.value.lower() == 'yes' for result in element_results if result.metadata['element_name'] == element_name)

        # Recursive function to add nodes and edges to the graph for the entire decision tree
        def add_to_graph(tree, parent_id=None, parent_element_name=None, decision_made=None, created_nodes=created_nodes):
            # Connect outcome nodes to their parent.
            if isinstance(tree, str):
                # Connect to the appropriate outcome node
                outcome_node_id = outcome_nodes[tree.lower()]
                if parent_id is not None:
                    edge_color = '#999999'
                    edge_penwidth = '1'
                    # Check if this is the final decision leading to the outcome
                    if tree.lower() == final_outcome:
                        # Check if the decision that led to this outcome node is part of the actual decision path
                        if any(result.metadata['element_name'] == CompositeScore.normalize_element_name(parent_element_name) and result.value.lower() == decision_made.lower() for result in element_results):
                            edge_color = '#000000'  # Dark color for the final decision edge
                            edge_penwidth = '3'  # Thicker edge for the final decision
                    logging.debug(f"Creating edge from {parent_id} to {outcome_node_id} with label {decision_made}")
                    dot.edge(parent_id, outcome_node_id, label=decision_made, color=edge_color, fontcolor=edge_color, penwidth=edge_penwidth, labeldistance='5')
                return
            
            # Check if the node has already been created
            if tree['element'] in created_nodes:
                node_id = created_nodes[tree['element']]
            else:
                node_id = f"node_{len(created_nodes)}"
                created_nodes[tree['element']] = node_id
                decision_label = tree['element']
                normalized_decision_label = CompositeScore.normalize_element_name(decision_label)
                it_was_positive = was_element_positive(normalized_decision_label, element_results)
                node_color = '#339933' if it_was_positive else '#DD3333' if normalized_decision_label in [result.metadata['element_name'] for result in element_results] else '#666666'
                dot.node(node_id, decision_label, style='filled, rounded', color=node_color, fontcolor='white')

            # Connect decision nodes to their parent.
            logging.debug(f"Creating edge from {parent_id} to {node_id} with label {decision_made}")
            if parent_id is not None:
                parent_decision_result = was_element_positive(CompositeScore.normalize_element_name(parent_element_name), element_results)
                did_decision_happen = did_element_decision_happen(CompositeScore.normalize_element_name(normalized_decision_label), element_results)
                if did_decision_happen and decision_made == 'yes' and parent_decision_result:
                    dot.edge(parent_id, node_id, label=decision_made, penwidth='3', labeldistance='5')
                elif did_decision_happen and decision_made == 'no' and not parent_decision_result:
                    dot.edge(parent_id, node_id, label=decision_made, penwidth='3', labeldistance='5')
                else:
                    dot.edge(parent_id, node_id, label=decision_made, color='#999999', fontcolor='#999999', labeldistance='5')
                
            # Recursive calls for true and false branches
            if True in tree:
                add_to_graph(tree[True], node_id, tree['element'], 'yes', created_nodes)
            if True in tree:
                add_to_graph(tree[False], node_id, tree['element'], 'no', created_nodes)

        # Start adding nodes and edges from the root of the decision tree
        add_to_graph(decision_tree)

        # Render the graph to a file
        with open(f"{filename}.dot", "w") as dotfile:
            dotfile.write(dot.source)
        dot.render(filename, format='png', view=False)
        return filename + '.png'

    def plot_scorecard_costs(self, results):

        sky_blue = np.array([0.0, 0.28, 0.67])
        fuchsia = np.array([0.815, 0.2, 0.51])
        teal = np.array([0, 0.5, 0.5])
        purple = np.array([0.5, 0, 0.5])
        forest_green = np.array([0.133, 0.545, 0.133])
        burnt_orange = np.array([0.8, 0.333, 0.0])
        deep_forest_green = np.array([0.0, 0.39, 0.0])
        bluish_grey = np.array([0.4, 0.5, 0.55])

        colors = [sky_blue, fuchsia, teal, purple, forest_green, burnt_orange, deep_forest_green, bluish_grey]

        def plot_input_output_costs():
            total_input_costs = {}
            total_output_costs = {}

            for result in results:
                for score_name, score_result in result['results'].items():
                    if score_name not in total_input_costs:
                        total_input_costs[score_name] = 0
                        total_output_costs[score_name] = 0
                        
                    metadata = score_result.get('metadata', {})
                    total_input_costs[score_name] += float(metadata.get('input_cost', 0))
                    total_output_costs[score_name] += float(metadata.get('output_cost', 0))

            score_names = list(total_input_costs.keys())
            input_costs = [total_input_costs[name] for name in score_names]
            output_costs = [total_output_costs[name] for name in score_names]

            x = np.arange(len(score_names))
            width = 0.35

            fig, ax = plt.subplots(figsize=(6, 6))
            ax.bar(x - width/2, input_costs, width, label='Input Costs', color=sky_blue)
            ax.bar(x + width/2, output_costs, width, label='Output Costs', color=fuchsia)

            ax.set_ylabel('Costs')
            ax.set_title('Costs by score and type')
            ax.set_xticks(x)
            ax.set_xticklabels(score_names, rotation=45, ha="right")
            ax.legend()

            fig.tight_layout()
            plt.savefig('mlruns/scorecard_input_output_costs.png')
            plt.close(fig)

        def plot_histogram_of_total_costs():
            total_costs = []

            for result in results:
                result_total_cost = 0
                for score_result in result['results'].values():
                    for element_result in score_result.get('element_results', []):
                        result_total_cost += element_result.metadata.get('total_cost', 0)
                total_costs.append(result_total_cost)

            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(total_costs, bins=20, color=sky_blue, edgecolor=bluish_grey)
            ax.set_title('Histogram of Total Costs for Different Results')
            ax.set_xlabel('Total Cost')
            ax.set_ylabel('Number of Results')
            ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))

            plt.savefig('mlruns/histogram_of_total_costs.png')
            plt.close(fig)

        def plot_distribution_of_costs():
            total_input_costs = {}

            for result in results:
                for score_name, score_result in result['results'].items():
                    metadata = score_result.get('metadata', {})
                    total_input_costs[score_name] = total_input_costs.get(score_name, 0) + float(metadata.get('input_cost', 0))

            score_names = list(total_input_costs.keys())
            input_costs = [total_input_costs[name] for name in score_names]

            fig, ax = plt.subplots(figsize=(6, 6))
            pie_wedges = ax.pie(input_costs, labels=score_names, autopct='%1.1f%%', startangle=140, colors=colors[:len(score_names)])
            plt.setp(pie_wedges[2], color='w')  # Set the color of the autopct texts to white
            ax.set_title('Distribution of Input Costs')

            plt.savefig('mlruns/distribution_of_input_costs.png')
            plt.close(fig)

        def plot_distribution_of_costs_by_element_type():
            total_costs = {}

            for result in results:
                for score_name, score_result in result['results'].items():
                    for element_result in score_result.get('llm_request_history', []):
                        element_type = element_result.get('element_type', 'unknown')
                        total_costs[element_type] = element_result.get('total_cost', 0)

            element_types = list(total_costs.keys())
            input_costs = [total_costs[element_type] for element_type in element_types]

            fig, ax = plt.subplots(figsize=(6, 6))
            pie_wedges = ax.pie(input_costs, labels=element_types, autopct='%1.1f%%', startangle=140, colors=colors[:len(element_types)])
            plt.setp(pie_wedges[2], color='w')  # Set the color of the autopct texts to white
            ax.set_title('Distribution of Input Costs by Element Type')

            plt.savefig('mlruns/distribution_of_input_costs_by_element_type.png')
            plt.close(fig)

        def plot_total_llm_calls_by_score():
            total_llm_calls = {}

            for result in results:
                for score_name, score_result in result['results'].items():
                    metadata = score_result.get('metadata', {})
                    llm_calls = int(metadata.get('llm_request_count', 0))
                    total_llm_calls[score_name] = total_llm_calls.get(score_name, 0) + llm_calls

            score_names = list(total_llm_calls.keys())
            llm_calls_counts = [total_llm_calls[name] for name in score_names]

            fig, ax = plt.subplots(figsize=(6, 6))
            ax.bar(score_names, llm_calls_counts, color=purple)
            ax.set_ylabel('Total LLM Calls')
            ax.set_title('Total LLM Calls by Score')
            ax.set_xticks(np.arange(len(score_names)))
            ax.set_xticklabels(score_names, rotation=45, ha="right")
            ax.yaxis.get_major_locator().set_params(integer=True)

            fig.tight_layout()
            plt.savefig('mlruns/total_llm_calls_by_score.png')
            plt.close(fig)

        os.makedirs('mlruns', exist_ok=True)

        plot_input_output_costs()
        plot_histogram_of_total_costs()
        plot_distribution_of_costs()
        plot_distribution_of_costs_by_element_type()
        plot_total_llm_calls_by_score()

    def generate_csv_scorecard_report(self, *, results):
        report = "session_id,question_name,human_label,result_value,correct_value\n"

        for scorecard_result in results:
            for question_name, score_result in scorecard_result['results'].items():
                report += f"{scorecard_result['session_id']}, {question_name}, {score_result['human_label']}, {score_result['value']}, ,\n"
                        
        return report