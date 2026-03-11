#!/bin/bash
set -e
cd /Users/ryan.porter/Projects/Plexus
# Group 1: SelectQuote
python scripts/run_vector_topic_memory_report.py --scorecard 1461 --days 180
python scripts/run_vector_topic_memory_report.py --scorecard 1481 --days 180
python scripts/run_vector_topic_memory_report.py --scorecard 1514 --days 180
python scripts/run_vector_topic_memory_report.py --scorecard 1515 --days 180

# Group 2: Others
python scripts/run_vector_topic_memory_report.py --scorecard 97 --days 180
python scripts/run_vector_topic_memory_report.py --scorecard 1039 --days 180
python scripts/run_vector_topic_memory_report.py --scorecard 731 --days 180
python scripts/run_vector_topic_memory_report.py --scorecard 765 --days 180
python scripts/run_vector_topic_memory_report.py --scorecard 1033 --days 180
python scripts/run_vector_topic_memory_report.py --scorecard 1462 --days 180
