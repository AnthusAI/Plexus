import os
import pandas as pd
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from call_criteria_database import DB, Report, VWForm, VWCalibrationForm, FormScore, FormQScore, QuestionAnswer
from .DataCache import DataCache
from call_criteria_database.session_viewed import SessionViewed
from pydantic import Field
import logging
from sqlalchemy.exc import SQLAlchemyError
import json
from rich.progress import Progress, TimeElapsedColumn, TimeRemainingColumn
from datetime import datetime
import hashlib

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
        DB.initialize(self.db_server, self.db_name, self.db_user, self.db_pass)
        logging.debug(f"Initialized CallCriteriaDBCache with DB server {self.db_server}")

    def initialize_db(self):
        DB.initialize(self.db_server, self.db_name, self.db_user, self.db_pass)
        return sessionmaker(bind=DB.get_engine())()

    def load_dataframe(self, *, data, fresh=False):
        if 'searches' in data:
            return self.load_from_searches(data, fresh)
        if 'queries' in data:
            return self.load_from_queries(data, fresh)
        logging.warning("No 'searches' or 'queries' found in data.")
        return pd.DataFrame()

    def save_to_cache(self, df, identifier):
        cache_file = self._get_cache_file_path(identifier)
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        df.to_parquet(cache_file)

    def cache_exists(self, identifier):
        cache_file = self._get_cache_file_path(identifier)
        return os.path.exists(cache_file)

    def load_from_cache(self, identifier):
        cache_file = self._get_cache_file_path(identifier)
        return pd.read_parquet(cache_file)

    def _get_cache_file_path(self, identifier):
        cache_dir = os.path.join(self.local_cache_directory, 'dataframes')
        os.makedirs(cache_dir, exist_ok=True)
        cache_filename = f"{identifier}.parquet"
        return os.path.join(cache_dir, cache_filename)

    def load_from_searches(self, data, fresh):
        searches = data.get('searches', [])
        unique_identifier = self.generate_unique_search_identifier(searches)

        if not fresh and self.cache_exists(unique_identifier):
            df = self.load_from_cache(unique_identifier)
            if 'scorecard_id' in df.columns and 'content_id' in df.columns:
                df['text'] = df.apply(
                    lambda row: self.get_report_transcript_text(row['scorecard_id'], row['content_id']),
                    axis=1
                )
                non_empty_text = df['text'].astype(bool).sum()
                logging.info(f"Loaded {non_empty_text} non-empty transcripts out of {len(df)} rows")
                self.save_to_cache(df, unique_identifier)
                logging.info(f"Updated cached dataframe saved")
                return df
            else:
                logging.error("Cached dataframe is missing 'scorecard_id' or 'content_id' columns.")

        logging.info(f"Processing {len(searches)} search configurations.")
        form_ids = self.collect_form_ids(searches)
        logging.info(f"Total form IDs collected: {len(form_ids)}")
        
        results = self.process_form_ids(form_ids)
        
        if results:
            dataframe = pd.DataFrame(results)
            logging.info(f"Dataframe created with {len(dataframe)} records and {len(dataframe.columns)} columns.")
            non_empty_text = dataframe['text'].astype(bool).sum()
            logging.info(f"Loaded {non_empty_text} non-empty transcripts out of {len(dataframe)} rows")
            logging.info(dataframe[['scorecard_id', 'content_id', 'text']].head().to_string())
            self.save_to_cache(dataframe, unique_identifier)
            logging.info(f"Cached dataframe saved")
        else:
            logging.warning("No data was loaded. Returning empty DataFrame.")
            dataframe = pd.DataFrame()
        
        logging.info(
            dataframe[['content_id', 'form_id', 'Good Call comment', 'text']]
            .head(3)
            .assign(text=dataframe['text'].str[:256])
            .to_string(index=False)
        )
        return dataframe

    def generate_unique_search_identifier(self, searches):
        search_identifiers = [
            f"{os.path.basename(search.get('item_list_filename', 'no_filename'))}_"
            f"{search.get('column_name', 'no_column')}_"
            f"{search.get('metadata_item', 'no_metadata')}_"
            f"{search.get('scorecard_id', 'no_scorecard')}"
            f"{search.get('score_id', 'no_score_id')}"
            for search in searches
        ]
        return "_".join(search_identifiers) or "default"

    def collect_form_ids(self, searches):
        form_ids = []
        for search in searches:
            item_list_filename = search.get('item_list_filename')
            if item_list_filename:
                df = (
                    pd.read_csv(item_list_filename) 
                    if item_list_filename.endswith('.csv') 
                    else pd.read_excel(item_list_filename)
                )
                form_ids.extend(df['form_id'].dropna().tolist())
        return form_ids

    def process_form_ids(self, form_ids):
        results = []
        with DB.get_session() as session:
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
                    batch_results = self.fetch_batch_from_db(batch, session)
                    logging.info(f"Retrieved {len(batch_results)} records from database")
                    
                    with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
                        futures = [executor.submit(self.process_report, row, session) for row in batch_results]
                        for future in as_completed(futures):
                            result = future.result()
                            if result is not None:
                                results.append(result)
                            progress.update(total_task, advance=1)
                    logging.info(f"Finished processing batch {i//self.batch_size + 1}")
        return results

    def fetch_batch_from_db(self, batch, session):
        query = select(
            Report.id.label('content_id'),
            VWForm.f_id.label('form_id'),
            Report.session_id,
            Report.scorecard_id,
            Report.date,
            Report.media_id,
            Report.transcribe_call
        ).join(
            VWForm, Report.id == VWForm.review_id
        ).filter(
            VWForm.f_id.in_(batch)
        )
        return session.execute(query).fetchall()

    def fetch_data_from_db(self, query, scorecard_id, number):
        with DB.get_session() as session:
            base_query = select(
                Report.id.label('content_id'),
                VWForm.f_id.label('form_id'),
                Report.session_id,
                Report.scorecard_id,
                Report.date,
                Report.media_id,
                Report.transcribe_call
            ).join(
                VWForm, Report.id == VWForm.review_id
            ).filter(
                Report.scorecard_id == scorecard_id
            ).filter(
                Report.media_id != None
            )

            if query.get('minimum_calibration_count'):
                min_calibration_count = query['minimum_calibration_count']
                calibration_count_subquery = session.query(
                    VWCalibrationForm.review_id,
                    func.count(VWCalibrationForm.id).label('calibration_count')
                ).group_by(
                    VWCalibrationForm.review_id
                ).having(
                    func.count(VWCalibrationForm.id) >= min_calibration_count
                ).subquery()

                base_query = base_query.join(
                    calibration_count_subquery,
                    Report.id == calibration_count_subquery.c.review_id
                )

            score_id = query.get('score_id')
            answer = query.get('answer')
            if score_id is not None:
                base_query = base_query.join(FormQScore, VWForm.f_id == FormQScore.form_id)
                if answer:
                    base_query = base_query.join(
                        QuestionAnswer, FormQScore.question_answered == QuestionAnswer.id
                    ).filter(
                        FormQScore.question_id == score_id,
                        QuestionAnswer.answer_text == answer
                    )
                else:
                    base_query = base_query.filter(
                        FormQScore.question_id == score_id,
                        FormQScore.question_answered != None
                    )

            reviewer = query.get('reviewer')
            if reviewer:
                base_query = base_query.join(SessionViewed, VWForm.review_id == SessionViewed.session_id)
                base_query = base_query.filter(SessionViewed.agent == reviewer)

            final_query = base_query.limit(number)

            logging.debug(f"Query: {final_query}")
            logging.info(
                f"Compiled SQL: {final_query.compile(compile_kwargs={'literal_binds': True})}"
            )
            
            result = session.execute(final_query).fetchall()
            
            logging.info(f"First Result: {result[0] if result else 'No results'}")
            
            return result

    def load_from_queries(self, data, fresh=False):
        queries = data.get('queries', [])
        unique_identifier = self.generate_unique_query_identifier(queries)
        
        if not fresh and self.cache_exists(unique_identifier):
            return self.load_from_cache(unique_identifier)
        
        all_results = []
        engine = DB.get_engine()
        SessionFactory = sessionmaker(bind=engine)
        
        for query in queries:
            if 'query' in query:
                logging.info(f"Executing custom query: {query['query']}")
                with SessionFactory() as session:
                    query_results = self.execute_custom_query(query, session)
            else:
                logging.info(f"Executing standard query with parameters: {query}")
                scorecard_id = query['scorecard_id']
                number = query['number']
                with SessionFactory() as session:
                    query_results = self.fetch_data_from_db(query, scorecard_id, number)
            
            logging.info(f"Query returned {len(query_results)} results")
            
            with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
                futures = [executor.submit(self.process_report, row, SessionFactory) for row in query_results]
                for future in as_completed(futures):
                    result = future.result()
                    if result is not None:
                        all_results.append(result)
        
        df = pd.DataFrame(all_results)
        
        self.save_to_cache(df, unique_identifier)
        
        return df

    def execute_custom_query(self, query_config, session):
        query_template = query_config['query']
        params = {k: v for k, v in query_config.items() if k != 'query'}
        
        # Ensure the query selects scorecard_id
        if 'scorecard_id' not in query_template.lower():
            query_template = query_template.replace("SELECT TOP", "SELECT TOP {number} a.scorecard,")
        
        sql = text(query_template.format(**params))
        
        logging.info(f"Executing custom SQL: {sql}")
        
        result = session.execute(sql)
        
        # Fetch the results and create a list of dictionaries
        columns = result.keys()
        results = [dict(zip(columns, row)) for row in result.fetchall()]
        
        logging.info(f"Custom query returned {len(results)} results")
        if results:
            logging.info(f"First result: {results[0]}")
        
        return results

    def generate_unique_query_identifier(self, queries):
        query_strings = []
        for query in queries:
            if 'query' in query:
                # For custom queries, use a hash of the query and other parameters
                query_str = f"custom_{query.get('scorecard_id', '')}_{query.get('number', '')}"
                query_hash = hashlib.md5(query['query'].encode()).hexdigest()[:8]
                query_str += f"_{query_hash}"
            else:
                # For standard queries, use the existing method
                query_str = "_".join(f"{key}_{value}" for key, value in query.items())
            query_strings.append(query_str)
        return "_".join(sorted(query_strings))

    def get_report_metadata(self, scorecard_id, report_id):
        metadata_file_path = self._get_metadata_file_path(scorecard_id, report_id)
        
        if os.path.exists(metadata_file_path):
            with open(metadata_file_path, 'r') as metadata_file:
                cached_data = json.load(metadata_file)
                cached_data['scorecard_id'] = cached_data.get('scorecard_id')
                cached_data['content_id'] =   cached_data.get('content_id')
                cached_data['form_id'] =      cached_data.get('form_id')
                cached_data['session_id'] =   cached_data.get('session_id')
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
            logging.debug(f"Transcript file not found: {transcript_file_path}")
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
        with DB.get_session() as session:
            report_obj = session.query(Report).get(report_id)
            if not report_obj:
                logging.error(f"Report with id {report_id} not found in database")
                return None

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

    def process_report(self, report, session_factory):
        if isinstance(report, dict):
            scorecard_id = report.get('scorecard_id')
            f_id = report.get('f_id')
        else:
            scorecard_id = report.scorecard_id
            f_id = report.f_id

        if not scorecard_id or not f_id:
            logging.error(f"Missing scorecard_id or f_id for report {report}")
            return None

        # Create a new session for this report processing
        with session_factory() as session:
            # Fetch the Report object using f_id
            vw_form = session.query(VWForm).filter(VWForm.f_id == f_id).first()
            if not vw_form:
                logging.error(f"VWForm with f_id {f_id} not found in database")
                return None

            content_id = vw_form.review_id

            with ThreadPoolExecutor() as executor:
                metadata_future = executor.submit(self.get_report_metadata, scorecard_id, content_id)
                transcript_future = executor.submit(self.get_report_transcript_text, scorecard_id, content_id)

                metadata = metadata_future.result()
                transcript_text = transcript_future.result()

            if not metadata:
                report_obj = session.query(Report).get(content_id)
                if not report_obj:
                    logging.error(f"Report with id {content_id} not found in database")
                    return None
                report_dict = {
                    'scorecard_id': scorecard_id,
                    'content_id': content_id,
                    'form_id': f_id,
                    'session_id': vw_form.session_id,
                    'date': report_obj.date,
                    'media_id': report_obj.media_id,
                }
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
            "form_id": f_id,
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
        with DB.get_session() as session:
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