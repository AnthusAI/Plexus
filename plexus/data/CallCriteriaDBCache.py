import os
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from call_criteria_database import DB, Report, VWForm
from .DataCache import DataCache
from pydantic import Field
import logging
from sqlalchemy.exc import SQLAlchemyError
import json
from rich.progress import Progress, TimeElapsedColumn, TimeRemainingColumn
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class CallCriteriaDBCache(DataCache):
    class Parameters(DataCache.Parameters):
        db_server: str = Field(default_factory=lambda: os.getenv('DB_SERVER'))
        db_name: str = Field(default_factory=lambda: os.getenv('DB_NAME'))
        db_user: str = Field(default_factory=lambda: os.getenv('DB_USER'))
        db_pass: str = Field(default_factory=lambda: os.getenv('DB_PASS'))
        # searches: list = Field(...)
        cache_file: str = Field(default="call_criteria_cache.h5")
        batch_size: int = Field(default=1000)
        local_cache_directory: str = Field(default_factory=lambda: './.plexus_training_data_cache/')
        thread_count: int = Field(default=os.cpu_count())

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.local_cache_directory = parameters.get('local_cache_directory', './.plexus_training_data_cache/')
        os.makedirs(self.local_cache_directory, exist_ok=True)
        self.db_server = self.parameters.db_server
        self.db_name = self.parameters.db_name
        self.db_user = self.parameters.db_user
        self.db_pass = self.parameters.db_pass
        self.cache_file = self.parameters.cache_file
        self.batch_size = self.parameters.batch_size
        self.thread_count = self.parameters.thread_count
        if not all([self.db_server, self.db_name, self.db_user, self.db_pass]):
            raise ValueError("Database credentials are missing.")
        logging.debug(f"Initialized CallCriteriaDBCache with DB server {self.db_server}")

    def initialize_db(self):
        DB.initialize(self.db_server, self.db_name, self.db_user, self.db_pass)
        return sessionmaker(bind=DB.get_engine())()

    def load_dataframe(self, *, data, fresh=False):
        if not fresh and os.path.exists(self.cache_file):
            logging.info(f"Loading cached dataframe from {self.cache_file}")
            df = pd.read_hdf(self.cache_file, key='dataframe')
            
            if 'scorecard_id' not in df.columns or 'content_id' not in df.columns:
                logging.error("Cached dataframe is missing 'scorecard_id' or 'content_id' columns.")
                return pd.DataFrame()

            logging.info("Reloading transcript text for all rows")
            df['text'] = df.apply(
                lambda row: self.get_report_transcript_text(row['scorecard_id'], row['content_id']),
                axis=1
            )

            non_empty_text = df['text'].astype(bool).sum()
            logging.info(f"Loaded {non_empty_text} non-empty transcripts out of {len(df)} rows")
            
            df.to_hdf(self.cache_file, key='dataframe', mode='w')
            logging.info(f"Updated cached dataframe saved to {self.cache_file}")
            
            return df

        searches = data.get('searches', [])
        logging.info(f"Processing {len(searches)} search configurations.")
        form_ids = []
        for search in searches:
            item_list_filename = search.get('item_list_filename')
            if item_list_filename:
                df = pd.read_csv(item_list_filename) if item_list_filename.endswith('.csv') else pd.read_excel(item_list_filename)
                form_ids.extend(df['form_id'].dropna().tolist())
        
        logging.info(f"Total form IDs collected: {len(form_ids)}")
        
        session = self.initialize_db()
        results = []
        
        progress = Progress(
            "[progress.description]{task.description}",
            "[progress.percentage]{task.percentage:>3.0f}%",
            "{task.completed}/{task.total}",
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        )
        
        with progress:
            total_task = progress.add_task("Processing reports", total=len(form_ids))
            
            for i in range(0, len(form_ids), self.batch_size):
                batch = form_ids[i:i+self.batch_size]
                logging.info(f"Processing batch {i//self.batch_size + 1} of {len(form_ids)//self.batch_size + 1}")
                
                query = select(Report.id.label('content_id'),
                               VWForm.f_id.label('form_id'),
                               Report.scorecard_id,
                               Report.date,
                               Report.media_id,
                               Report.transcribe_call)\
                        .join(VWForm, Report.id == VWForm.review_id)\
                        .filter(VWForm.f_id.in_(batch))
                
                batch_results = session.execute(query).fetchall()
                logging.info(f"Retrieved {len(batch_results)} records from database")
                
                SessionLocal = sessionmaker(bind=DB.get_engine())

                with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
                    futures = [executor.submit(self.process_report, report, SessionLocal()) 
                               for report in batch_results]
                    
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            if result is not None:
                                results.append(result)
                        except Exception as e:
                            logging.error(f"Error in future: {str(e)}")
                        finally:
                            progress.update(total_task, advance=1)

                logging.info(f"Finished processing batch {i//self.batch_size + 1}")
        
        session.close()
        
        if results:
            dataframe = pd.DataFrame(results)
            logging.info(f"Dataframe created with {len(dataframe)} records and {len(dataframe.columns)} columns.")
            
            non_empty_text = dataframe['text'].astype(bool).sum()
            logging.info(f"Loaded {non_empty_text} non-empty transcripts out of {len(dataframe)} rows")
            
            logging.info("Sample rows from the dataframe:")
            logging.info(dataframe[['scorecard_id', 'content_id', 'text']].head().to_string())
            
            dataframe.to_hdf(self.cache_file, key='dataframe', mode='w')
            logging.info(f"Cached dataframe saved to {self.cache_file}")
        else:
            logging.warning("No data was loaded. Returning empty DataFrame.")
            dataframe = pd.DataFrame()
        
        logging.info("First three rows of the dataframe:")
        logging.info(dataframe[['content_id', 'form_id', 'Good Call comment', 
                        'text']].head(3)
                     .assign(text=dataframe['text'].str[:256])
                     .to_string(index=False))

        return dataframe

    def get_report_metadata(self, scorecard_id, report_id):
        metadata_file_path = self._get_metadata_file_path(scorecard_id, report_id)
        
        if os.path.exists(metadata_file_path):
            with open(metadata_file_path, 'r') as metadata_file:
                cached_data = json.load(metadata_file)
                cached_data['scorecard_id'] = cached_data.get('scorecard_id')
                cached_data['content_id'] =   cached_data.get('content_id')
                cached_data['form_id'] =      cached_data.get('form_id')
                if 'searches' not in cached_data:
                    cached_data['searches'] = []
                return cached_data
        
        return None

    def get_report_transcript_text(self, scorecard_id, report_id):
        transcript_file_path = self._get_transcript_txt_path(scorecard_id, report_id)
        
        if os.path.exists(transcript_file_path):
            try:
                with open(transcript_file_path, 'r', encoding='utf-8') as file:
                    return file.read()
            except Exception as e:
                logging.error(f"Error reading transcript.txt for scorecard_id={scorecard_id}, report_id={report_id}: {str(e)}")
        else:
            logging.warning(f"Transcript file not found: {transcript_file_path}")
        return ''

    def store_report_transcript_text(self, scorecard_id, report_id, transcript_text):
        logging.debug(f"Storing transcript for scorecard_id={scorecard_id}, report_id={report_id}")
        transcript_file_path = self._get_transcript_txt_path(scorecard_id, report_id)
        os.makedirs(os.path.dirname(transcript_file_path), exist_ok=True)

        try:
            with open(transcript_file_path, 'w', encoding='utf-8') as file:
                file.write(transcript_text)
            logging.debug(f"Stored transcript.txt for scorecard_id={scorecard_id}, report_id={report_id}")
        except Exception as e:
            logging.error(f"Failed to store transcript.txt for scorecard_id={scorecard_id}, report_id={report_id}: {str(e)}")

    def store_report_metadata(self, scorecard_id, report_id, report_dict):
        logging.debug(f"Storing metadata for scorecard_id={scorecard_id}, report_id={report_id}")
        session = self.initialize_db()
        try:
            report_obj = session.query(Report).get(report_id)
            if not report_obj:
                logging.error(f"Report with id {report_id} not found in database")
                return

            results_data = report_obj.results()

            structured_data = {
                "transaction_key": "deprecated",
                "request_id": report_dict.get('media_id', ''),
                "created": report_dict.get('date'),
                "scores": [],
                "calibrations": report_obj.get_number_of_calibrations(),
                "miscalibration": report_obj.is_miscalibrated(),
                "calibration_match_rate": report_obj.compute_calibration_match_rate(),
                "form_id": report_dict.get('form_id', ''),
                "good_call": report_obj.is_good_call(),
                "good_call_confidence": report_obj.get_good_call_confidence(),
                "scorecard_id": scorecard_id,
                "content_id": report_id
            }

            for score_id, score_data in results_data.items():
                score = {
                    "id": int(score_id),
                    "name": score_data["name"],
                    "answer": score_data["answer"],
                    "comment": score_data["comment"],
                    "position": score_data.get("position", ""),
                    "confidence": score_data.get("confidence"),
                    "calibration_answers_match": score_data.get(
                        "calibration_answers_match", False
                    ),
                    "calibration_comments_match": score_data.get(
                        "calibration_comments_match", False
                    )
                }
                structured_data["scores"].append(score)

            good_call_score = {
                "id": 0,
                "name": "Good Call",
                "answer": "Yes" if structured_data["good_call"] else "No",
                "comment": report_obj.get_bad_call_reason(),
                "confidence": structured_data["good_call_confidence"],
                "position": "",
                "calibration_answers_match": False,
                "calibration_comments_match": False
            }
            structured_data["scores"].append(good_call_score)

            report_dict["Good Call"] = good_call_score["answer"]
            report_dict["Good Call comment"] = good_call_score["comment"]
            report_dict["Good Call confidence"] = good_call_score["confidence"]

            metadata_file_path = self._get_metadata_file_path(scorecard_id, report_id)
            os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

            with open(metadata_file_path, 'w') as metadata_file:
                json.dump(structured_data, metadata_file, indent=2, cls=DateTimeEncoder)

            logging.debug(f"Stored metadata for scorecard_id={scorecard_id}, report_id={report_id}")

            # Store the transcript text separately using the new method
            transcript_text = report_obj.transcript(session=session)
            self.store_report_transcript_text(scorecard_id, report_id, transcript_text)

        finally:
            session.close()

        return structured_data

    def store_report_transcript_json(self, scorecard_id, report_id, transcript_json_data):
        transcript_file_path = self._get_transcript_json_path(scorecard_id, report_id)
        os.makedirs(os.path.dirname(transcript_file_path), exist_ok=True)

        with open(transcript_file_path, 'w', encoding='utf-8') as transcript_file:
            json.dump(transcript_json_data, transcript_file, indent=2)

        logging.debug(f"Stored transcript.json for scorecard_id={scorecard_id}, report_id={report_id}")

    def _get_metadata_file_path(self, scorecard_id, report_id):
        return os.path.join(
            self.local_cache_directory,
            'content_items',
            f'scorecard_id={scorecard_id}',
            f'report_id={report_id}',
            'metadata.json'
        )

    def _get_transcript_txt_path(self, scorecard_id, report_id):
        return os.path.join(
            self.local_cache_directory,
            'content_items',
            f'scorecard_id={scorecard_id}',
            f'report_id={report_id}',
            'transcript.txt'
        )

    def _get_transcript_json_path(self, scorecard_id, report_id):
        return os.path.join(
            self.local_cache_directory,
            'content_items',
            f'scorecard_id={scorecard_id}',
            f'report_id={report_id}',
            'transcript.json'
        )

    def process_report(self, report, session):
        scorecard_id = report.scorecard_id
        content_id = report.content_id

        if not scorecard_id or not content_id:
            logging.error(f"Missing scorecard_id or content_id for report {report}")
            return None

        with ThreadPoolExecutor() as executor:
            metadata_future = executor.submit(self.get_report_metadata, scorecard_id, content_id)
            transcript_future = executor.submit(self.get_report_transcript_text, scorecard_id, content_id)

            metadata = metadata_future.result()
            transcript_text = transcript_future.result()

        if not metadata:
            report_dict = report._asdict()
            metadata = self.store_report_metadata(scorecard_id, content_id, report_dict)
            if not metadata:
                return None

        if not transcript_text:
            transcript_text = self.fetch_and_store_transcript(scorecard_id, content_id, session)
            if not transcript_text:
                logging.error(f"Failed to retrieve transcript for scorecard_id={scorecard_id}, content_id={content_id}")
                return None

        result = {
            "scorecard_id": scorecard_id,
            "content_id": content_id,
            "form_id": metadata.get('form_id'),
            "text": transcript_text
        }

        scores = metadata.get("scores", [])
        for score in scores:
            score_name = score.get("name", f"Unknown_{score.get('id', 'N/A')}")
            result[score_name] = score.get("answer", "")
            result[f"{score_name} comment"] = score.get("comment", "")
            confidence = score.get("confidence")
            if confidence is not None:
                result[f"{score_name} confidence"] = confidence

        return result

    def fetch_and_store_transcript(self, scorecard_id, content_id, session):
        logging.debug(f"Fetching transcript for scorecard_id={scorecard_id}, content_id={content_id}")

        report_obj = session.query(Report).get(content_id)
        if not report_obj:
            logging.error(f"Report with id {content_id} not found in database")
            return None

        transcript_text = report_obj.transcript(session=session)
        if transcript_text:
            self.store_report_transcript_text(scorecard_id, content_id, transcript_text)
            return transcript_text
        logging.error(f"Transcript text is empty for scorecard_id={scorecard_id}, content_id={content_id}")
        return None