import os
import pandas as pd
import importlib
import builtins
import rich
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.pretty import pprint
from plexus.CustomLogging import logging, console

class ScoreData:

    def load_data(self, *, data=None, excel=None, fresh=False):
        """
        Load the specified data from the training data lake, with caching, into a combined DataFrame in the class instance.

        Parameters
        ----------
        data : dict, optional
            Dictionary of data to load from the training data lake.
        excel : str, optional
            Path to an Excel file to load data from.
        """
        data_cache = self._load_data_cache()

        self.dataframe = data_cache.load_dataframe(data=data, fresh=fresh)

        logging.debug(f"Loaded dataframe: {self.dataframe.head().to_string()}")
        
        # Apply dependency filters if they exist
        if self.parameters.dependencies:

            logging.info(f"Applying dependency filters.  Rows before: {len(self.dataframe)}")

            for dependency in self.parameters.dependencies:
                for column, condition in dependency.items():
                    logging.info(f"Applying dependency filter: {column} == {condition['value']}")
                    self.dataframe = self.dataframe[self.dataframe[column] == condition['value']]
            
            logging.info(f"Applied dependency filters.  Rows after: {len(self.dataframe)}")

        # Display the first few rows of the dataframe
        logging.debug(f"First few rows of the dataframe:")
        logging.debug(self.dataframe.head().to_string())

        self.analyze_dataset()

        return self.dataframe

    def _load_data_cache(self):
        data_cache_class_path = self.parameters.data['class']
        
        # Check if the provided class path includes a module or is just the class name
        if '.' in data_cache_class_path:
            # Full module path specified, split it into module and class name
            module_name, class_name = data_cache_class_path.rsplit('.', 1)
        else:
            # Only class name provided, default to 'plexus.data'
            module_name = 'plexus.data'
            class_name = data_cache_class_path
        
        try:
            # First, attempt to import the specified module and retrieve the class
            module = importlib.import_module(module_name)
            data_cache_class = getattr(module, class_name)
        except (ImportError, AttributeError):
            # Fallback to check in `plexus_extensions`
            try:
                module = importlib.import_module(f'plexus_extensions.{class_name}')
                data_cache_class = getattr(module, class_name)
                logging.info(f"Loaded {class_name} from plexus_extensions.{class_name}")
            except (ImportError, AttributeError):
                # Fallback to check in `builtins`
                if hasattr(builtins, class_name):
                    data_cache_class = getattr(builtins, class_name)
                    logging.info(f"Loaded {class_name} from builtins namespace")
                else:
                    # Raise an error if the class is not found anywhere
                    raise ImportError(f"Cannot find class {class_name} in module {module_name}, plexus_extensions.{class_name}, or builtins namespace")
        
        # Return an instance of the loaded class
        return data_cache_class(**self.parameters.data)

    def analyze_dataset(self):
        """
        Analyze the loaded dataset and display various summaries and breakdowns.
        """
        panels = []

        answer_breakdown_table = Table(
            title="[royal_blue1][b]Answer Breakdown[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        answer_breakdown_table.add_column("Answer", justify="right", style="royal_blue1", no_wrap=True)
        answer_breakdown_table.add_column("Count", style="magenta1", justify="right")
        answer_breakdown_table.add_column("Percentage", style="magenta1 bold", justify="right")

        score_name = self.get_label_score_name()

        try:
            answer_counts = self.dataframe[score_name].value_counts()
            total_responses = answer_counts.sum()
            for answer_value, count in answer_counts.items():
                percentage_of_total = (count / total_responses) * 100
                formatted_percentage = f"{percentage_of_total:.1f}%"
                answer_breakdown_table.add_row(str(answer_value), str(count), formatted_percentage)
        except KeyError:
            pass

        panels.append(Panel(answer_breakdown_table, border_style="royal_blue1"))

        dataframe_summary_title = "[royal_blue1][b]Dataframe Summary[/b][/royal_blue1]"
        dataframe_summary_table = Table(
            title=dataframe_summary_title,
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        dataframe_summary_table.add_column("Description", justify="right", style="royal_blue1", no_wrap=True)
        dataframe_summary_table.add_column("Value", style="magenta1", justify="right")
        dataframe_summary_table.add_row("Number of Rows", str(self.dataframe.shape[0]), style="magenta1 bold")
        dataframe_summary_table.add_row("Number of Columns", str(self.dataframe.shape[1]))
        dataframe_summary_table.add_row("Total Cells", str(self.dataframe.size))

        if 'answer_counts' in locals():
            smallest_answer_count = answer_counts.min()
            total_kinds_of_non_null_answers = self.dataframe[score_name].nunique()
            total_balanced_count = smallest_answer_count * total_kinds_of_non_null_answers

            dataframe_summary_table.add_row("Smallest Count", str(smallest_answer_count))
            dataframe_summary_table.add_row("Total Balanced Count", str(total_balanced_count), style="magenta1 bold")
        panels.append(Panel(dataframe_summary_table, border_style="royal_blue1"))

        column_names_table = Table(
            title="[royal_blue1][b]Column Names[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        column_names_table.add_column("Column Name", style="magenta1")
        for column_name in self.dataframe.columns:
            column_names_table.add_row(column_name)

        panels.append(Panel(column_names_table, border_style="royal_blue1"))

        columns = Columns(panels)
        header_text = f"[bold royal_blue1]{score_name}[/bold royal_blue1]"

        rich.print(Panel(columns, title=header_text, border_style="magenta1"))

    def process_data(self):
        """
        Handle any pre-processing of the training data, including the training/validation splits.
        """
        score_name = self.get_label_score_name()

        # Drop NaN values in the column specified by score_name
        if score_name in self.dataframe.columns:
            self.dataframe = self.dataframe.dropna(subset=[score_name])

        if 'processors' in self.parameters.data:
            console.print(Text("Running configured processors...", style="royal_blue1"))

            processors = []
            for processor in self.parameters.data['processors']:
                processor_class = processor['class']
                processor_parameters = processor.get('parameters', {})
                from plexus.processors import ProcessorFactory
                processor_instance = ProcessorFactory.create_processor(processor_class, **processor_parameters)
                processors.append(processor_instance)

            first_transcript_before = self.dataframe['text'].iloc[0]

            for processor in processors:
                self.dataframe = processor.process(self.dataframe)

            first_transcript_after = self.dataframe['text'].iloc[0]

            if first_transcript_before and first_transcript_after:
                first_transcript_before_truncated = first_transcript_before[:1000] + '...'
                first_transcript_after_truncated = first_transcript_after[:1000] + '...'

                transcript_comparison_table = Table(
                    title=f"[royal_blue1][b]Processors[/b][/royal_blue1]",
                    header_style="sky_blue1",
                    border_style="sky_blue1"
                )
                transcript_comparison_table.add_column("Before", style="magenta1", justify="left")
                transcript_comparison_table.add_column("After", style="magenta1", justify="left")
                transcript_comparison_table.add_row(first_transcript_before_truncated, first_transcript_after_truncated)

                console.print(Panel(transcript_comparison_table, border_style="royal_blue1"))

        console.print(Text("Processed dataframe:", style="royal_blue1"))
        self.analyze_dataset()

        before_subsample_count = len(self.dataframe)
        self.dataframe = self.dataframe.sample(frac=self.parameters.data['percentage'] / 100, random_state=42)
        after_subsample_count = len(self.dataframe)

        subsample_comparison_table = Table(
            title=f"[royal_blue1][b]Subsampling {self.parameters.data['percentage']}% of the data[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        subsample_comparison_table.add_column("Before", style="magenta1", justify="left")
        subsample_comparison_table.add_column("After", style="magenta1", justify="left")
        subsample_comparison_table.add_row(str(before_subsample_count), str(after_subsample_count))

        console.print(Panel(subsample_comparison_table, border_style="royal_blue1"))

        if 'balance' in self.parameters.data and not self.parameters.data['balance']:
            logging.info("data->balance: [red][b]false.[/b][/red]  Skipping data balancing.")
            return

        if score_name in self.dataframe.columns:
            print("\nDistribution of labels in the dataframe:")
            print(self.dataframe[score_name].value_counts(dropna=False))

            unique_labels = self.dataframe[score_name].unique()

            label_dataframes = {label: self.dataframe[self.dataframe[score_name] == label] for label in unique_labels}

            for label, df in label_dataframes.items():
                print(f"Label '{label}' has {len(df)} instances.")

            smallest_class_size = min(len(df) for df in label_dataframes.values() if len(df) > 0)

            balanced_dataframes = []
            for label, dataframe in label_dataframes.items():
                if len(dataframe) > 0:
                    print(f"Sampling {smallest_class_size} instances from the '{label}' class...")
                    balanced_dataframes.append(dataframe.sample(n=smallest_class_size, random_state=42))

            balanced_dataframe = pd.concat(balanced_dataframes)

            balanced_dataframe = balanced_dataframe.sample(frac=1, random_state=42)

            print("\nDistribution of labels in the balanced dataframe:")
            print(balanced_dataframe[score_name].value_counts())

            self.dataframe = balanced_dataframe

            console.print(Text("Final, balanced dataframe:", style="royal_blue1"))
            self.analyze_dataset()