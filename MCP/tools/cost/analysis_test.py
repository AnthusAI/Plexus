#!/usr/bin/env python3
"""
Unit tests for cost analysis tools
"""
import pytest
import os
from unittest.mock import patch, Mock
from decimal import Decimal

pytestmark = pytest.mark.unit


class TestCostAnalysisTool:
    """Test plexus_cost_analysis tool patterns"""
    
    def test_cost_analysis_validation_patterns(self):
        """Test cost analysis parameter validation patterns"""
        def validate_cost_analysis_params(days=0, hours=1, scorecard=None, score=None, 
                                        group_by=None, mode="summary", breakdown=False):
            # Validate days parameter
            try:
                days_int = int(float(str(days)))
                if days_int < 0:
                    return False, "days must be non-negative"
            except (ValueError, TypeError):
                days_int = 0
            
            # Validate hours parameter  
            try:
                hours_int = int(float(str(hours)))
                if hours_int < 0:
                    return False, "hours must be non-negative"
            except (ValueError, TypeError):
                hours_int = 1
            
            # Validate mode parameter
            valid_modes = ["summary", "detail"]
            if mode not in valid_modes:
                return False, f"mode must be one of: {valid_modes}"
            
            # Validate group_by parameter
            valid_group_by = [None, "scorecard", "score", "scorecard_score"]
            if group_by not in valid_group_by:
                return False, f"group_by must be one of: {valid_group_by}"
            
            # Validate breakdown parameter
            if not isinstance(breakdown, bool):
                return False, "breakdown must be a boolean"
            
            # Validate score requires scorecard when both provided
            if score and not scorecard:
                return False, "score parameter requires scorecard parameter"
            
            return True, None
        
        # Test valid parameters - default
        valid, error = validate_cost_analysis_params()
        assert valid is True
        assert error is None
        
        # Test valid parameters - custom time window
        valid, error = validate_cost_analysis_params(days=7, hours=0)
        assert valid is True
        assert error is None
        
        # Test valid parameters - with scorecard and score
        valid, error = validate_cost_analysis_params(scorecard="test-scorecard", score="test-score")
        assert valid is True
        assert error is None
        
        # Test valid parameters - with grouping and breakdown
        valid, error = validate_cost_analysis_params(group_by="scorecard", breakdown=True)
        assert valid is True
        assert error is None
        
        # Test valid parameters - detail mode
        valid, error = validate_cost_analysis_params(mode="detail")
        assert valid is True
        assert error is None
        
        # Test invalid mode
        valid, error = validate_cost_analysis_params(mode="invalid")
        assert valid is False
        assert "mode must be one of" in error
        
        # Test invalid group_by
        valid, error = validate_cost_analysis_params(group_by="invalid")
        assert valid is False
        assert "group_by must be one of" in error
        
        # Test invalid breakdown type
        valid, error = validate_cost_analysis_params(breakdown="invalid")
        assert valid is False
        assert "breakdown must be a boolean" in error
        
        # Test score without scorecard
        valid, error = validate_cost_analysis_params(score="test-score")
        assert valid is False
        assert "score parameter requires scorecard parameter" in error
    
    def test_parameter_parsing_patterns(self):
        """Test parameter parsing patterns for days and hours"""
        def parse_time_params(days, hours):
            try:
                days_parsed = int(float(str(days)))
            except (ValueError, TypeError):
                days_parsed = 0
            
            try:
                hours_parsed = int(float(str(hours)))
            except (ValueError, TypeError):
                hours_parsed = 1
            
            return days_parsed, hours_parsed
        
        # Test valid integer inputs
        days, hours = parse_time_params(7, 24)
        assert days == 7
        assert hours == 24
        
        # Test valid float inputs
        days, hours = parse_time_params(7.5, 1.0)
        assert days == 7
        assert hours == 1
        
        # Test string number inputs
        days, hours = parse_time_params("3", "12")
        assert days == 3
        assert hours == 12
        
        # Test invalid inputs default to fallback values
        days, hours = parse_time_params("invalid", None)
        assert days == 0
        assert hours == 1
        
        # Test empty string inputs
        days, hours = parse_time_params("", "")
        assert days == 0
        assert hours == 1
    
    def test_scorecard_resolution_patterns(self):
        """Test scorecard resolution patterns"""
        def simulate_scorecard_resolution(scorecard_identifier):
            # Mock successful resolution
            mock_scorecards = {
                "test-scorecard": "scorecard-123",
                "scorecard-456": "scorecard-456",
                "Call Criteria": "scorecard-789"
            }
            return mock_scorecards.get(scorecard_identifier)
        
        # Test resolution by name
        resolved_id = simulate_scorecard_resolution("test-scorecard")
        assert resolved_id == "scorecard-123"
        
        # Test resolution by ID
        resolved_id = simulate_scorecard_resolution("scorecard-456")
        assert resolved_id == "scorecard-456"
        
        # Test resolution by display name
        resolved_id = simulate_scorecard_resolution("Call Criteria")
        assert resolved_id == "scorecard-789"
        
        # Test failed resolution
        resolved_id = simulate_scorecard_resolution("nonexistent")
        assert resolved_id is None
    
    def test_score_resolution_patterns(self):
        """Test score resolution within scorecard patterns"""
        # Mock scorecard data
        scorecard_data = {
            'id': 'scorecard-123',
            'name': 'Test Scorecard',
            'sections': {
                'items': [
                    {
                        'id': 'section-1',
                        'scores': {
                            'items': [
                                {
                                    'id': 'score-123',
                                    'name': 'Test Score',
                                    'key': 'test_score',
                                    'externalId': 'EXT-001'
                                },
                                {
                                    'id': 'score-456',
                                    'name': 'Another Score',
                                    'key': 'another_score',
                                    'externalId': 'EXT-002'
                                }
                            ]
                        }
                    }
                ]
            }
        }
        
        def resolve_score_in_scorecard(score_identifier, scorecard_data):
            for section in (scorecard_data.get('sections', {}) or {}).get('items', []) or []:
                for s in (section.get('scores', {}) or {}).get('items', []) or []:
                    name = s.get('name') or ''
                    if (
                        s.get('id') == score_identifier or
                        name.lower() == str(score_identifier).lower() or
                        s.get('key') == score_identifier or
                        s.get('externalId') == score_identifier or
                        str(score_identifier).lower() in name.lower()
                    ):
                        return s.get('id')
            return None
        
        # Test resolution by ID
        resolved_id = resolve_score_in_scorecard('score-123', scorecard_data)
        assert resolved_id == 'score-123'
        
        # Test resolution by name (exact match)
        resolved_id = resolve_score_in_scorecard('Test Score', scorecard_data)
        assert resolved_id == 'score-123'
        
        # Test resolution by name (case insensitive)
        resolved_id = resolve_score_in_scorecard('test score', scorecard_data)
        assert resolved_id == 'score-123'
        
        # Test resolution by key
        resolved_id = resolve_score_in_scorecard('test_score', scorecard_data)
        assert resolved_id == 'score-123'
        
        # Test resolution by external ID
        resolved_id = resolve_score_in_scorecard('EXT-001', scorecard_data)
        assert resolved_id == 'score-123'
        
        # Test resolution by partial name match
        resolved_id = resolve_score_in_scorecard('another', scorecard_data)
        assert resolved_id == 'score-456'
        
        # Test failed resolution
        resolved_id = resolve_score_in_scorecard('nonexistent', scorecard_data)
        assert resolved_id is None
    
    def test_cost_analyzer_patterns(self):
        """Test cost analyzer instantiation patterns"""
        def create_cost_analyzer(client, account_id, days, hours, scorecard_id=None, score_id=None):
            # Mock analyzer creation
            return {
                'client': client,
                'account_id': account_id,
                'days': days,
                'hours': hours,
                'scorecard_id': scorecard_id,
                'score_id': score_id
            }
        
        def analyze_costs(analyzer_config, group_by=None):
            # Mock analysis results
            mock_analysis = {
                'accountId': analyzer_config['account_id'],
                'days': analyzer_config['days'],
                'hours': analyzer_config['hours'],
                'filters': {
                    'scorecard_id': analyzer_config['scorecard_id'],
                    'score_id': analyzer_config['score_id']
                },
                'headline': {
                    'average_cost': 0.0025,
                    'count': 150,
                    'total_cost': 0.375,
                    'average_calls': 2.1
                },
                'groups': [] if not group_by else [
                    {
                        'group': {'scoreId': 'score-123'},
                        'average_cost': 0.003,
                        'count': 75,
                        'total_cost': 0.225
                    }
                ],
                'scoreNameIndex': {'score-123': 'Test Score'}
            }
            return mock_analysis
        
        # Test analyzer creation
        analyzer = create_cost_analyzer('mock_client', 'account-123', 1, 0, 'scorecard-456', 'score-789')
        assert analyzer['account_id'] == 'account-123'
        assert analyzer['days'] == 1
        assert analyzer['hours'] == 0
        assert analyzer['scorecard_id'] == 'scorecard-456'
        assert analyzer['score_id'] == 'score-789'
        
        # Test analysis without grouping
        analysis = analyze_costs(analyzer)
        assert analysis['headline']['average_cost'] == 0.0025
        assert analysis['headline']['count'] == 150
        assert len(analysis['groups']) == 0
        
        # Test analysis with grouping
        analysis = analyze_costs(analyzer, group_by='score')
        assert len(analysis['groups']) == 1
        assert analysis['groups'][0]['group']['scoreId'] == 'score-123'
    
    def test_summary_extraction_patterns(self):
        """Test summary extraction patterns"""
        def pick_summary(head):
            return {
                "average_cost": head.get("average_cost"),
                "count": head.get("count"),
                "total_cost": head.get("total_cost"),
                "average_calls": head.get("average_calls"),
            }
        
        # Test with complete data
        mock_headline = {
            'average_cost': 0.0025,
            'count': 150,
            'total_cost': 0.375,
            'average_calls': 2.1,
            'extra_field': 'ignored'
        }
        
        summary = pick_summary(mock_headline)
        assert summary['average_cost'] == 0.0025
        assert summary['count'] == 150
        assert summary['total_cost'] == 0.375
        assert summary['average_calls'] == 2.1
        assert 'extra_field' not in summary
        
        # Test with missing data
        incomplete_headline = {'count': 100}
        summary = pick_summary(incomplete_headline)
        assert summary['average_cost'] is None
        assert summary['count'] == 100
        assert summary['total_cost'] is None
        assert summary['average_calls'] is None
    
    def test_group_processing_patterns(self):
        """Test group processing and sorting patterns"""
        def process_groups(groups, name_index):
            groups_out = []
            for g in groups:
                label = dict(g.get("group", {}))
                # Attach human-friendly names when grouping by score
                if "scoreId" in label:
                    sid = label["scoreId"]
                    if sid in name_index:
                        label["scoreName"] = name_index[sid]
                groups_out.append({
                    "group": label,
                    "average_cost": g.get("average_cost"),
                    "count": g.get("count"),
                    "total_cost": g.get("total_cost"),
                    "average_calls": g.get("average_calls"),
                })
            return groups_out
        
        def sort_groups_by_cost(groups):
            def sort_key_cost(item):
                try:
                    return Decimal(item.get("average_cost") or "0")
                except Exception:
                    return Decimal("0")
            groups.sort(key=sort_key_cost, reverse=True)
            return groups
        
        # Mock groups data
        mock_groups = [
            {
                'group': {'scoreId': 'score-123'},
                'average_cost': 0.002,
                'count': 50,
                'total_cost': 0.1
            },
            {
                'group': {'scoreId': 'score-456'},
                'average_cost': 0.005,
                'count': 30,
                'total_cost': 0.15
            }
        ]
        
        name_index = {
            'score-123': 'First Score',
            'score-456': 'Second Score'
        }
        
        # Test group processing
        processed = process_groups(mock_groups, name_index)
        assert len(processed) == 2
        assert processed[0]['group']['scoreName'] == 'First Score'
        assert processed[1]['group']['scoreName'] == 'Second Score'
        
        # Test sorting by cost (highest first)
        sorted_groups = sort_groups_by_cost(processed)
        assert sorted_groups[0]['average_cost'] == 0.005  # Second Score
        assert sorted_groups[1]['average_cost'] == 0.002  # First Score
    
    def test_result_formatting_patterns(self):
        """Test result formatting patterns for summary and detail modes"""
        def format_summary_result(analysis, resolved_scorecard_id=None, resolved_scorecard_name=None, breakdown=False, group_by=None):
            def pick_summary(head):
                return {
                    "average_cost": head.get("average_cost"),
                    "count": head.get("count"),
                    "total_cost": head.get("total_cost"),
                    "average_calls": head.get("average_calls"),
                }
            
            result = {
                "success": True,
                "accountId": analysis.get("accountId"),
                "days": analysis.get("days"),
                "hours": analysis.get("hours"),
                "filters": analysis.get("filters"),
                "summary": pick_summary(analysis.get("headline", {})),
            }
            
            if resolved_scorecard_id:
                result["scorecardName"] = resolved_scorecard_name
            
            if breakdown and group_by in ("score", "scorecard", "scorecard_score"):
                result["groups"] = analysis.get("groups", [])
            
            return result
        
        def format_detail_result(analysis, resolved_scorecard_id=None, resolved_scorecard_name=None):
            detail = {"success": True, **analysis}
            if resolved_scorecard_id:
                detail["scorecardName"] = resolved_scorecard_name
            return detail
        
        # Mock analysis data
        mock_analysis = {
            'accountId': 'account-123',
            'days': 1,
            'hours': 0,
            'filters': {'scorecard_id': 'scorecard-456'},
            'headline': {
                'average_cost': 0.0025,
                'count': 150,
                'total_cost': 0.375,
                'average_calls': 2.1
            },
            'groups': [{'group': {'scoreId': 'score-123'}, 'average_cost': 0.003}],
            'extra_detail': 'detailed info'
        }
        
        # Test summary formatting without breakdown
        summary_result = format_summary_result(mock_analysis)
        assert summary_result['success'] is True
        assert summary_result['accountId'] == 'account-123'
        assert summary_result['summary']['average_cost'] == 0.0025
        assert 'groups' not in summary_result
        assert 'extra_detail' not in summary_result
        
        # Test summary formatting with breakdown
        summary_result = format_summary_result(mock_analysis, breakdown=True, group_by='score')
        assert 'groups' in summary_result
        assert len(summary_result['groups']) == 1
        
        # Test summary formatting with scorecard name
        summary_result = format_summary_result(mock_analysis, 'scorecard-456', 'Test Scorecard')
        assert summary_result['scorecardName'] == 'Test Scorecard'
        
        # Test detail formatting
        detail_result = format_detail_result(mock_analysis, 'scorecard-456', 'Test Scorecard')
        assert detail_result['success'] is True
        assert detail_result['accountId'] == 'account-123'
        assert detail_result['extra_detail'] == 'detailed info'
        assert detail_result['scorecardName'] == 'Test Scorecard'
    
    def test_error_handling_patterns(self):
        """Test various error handling patterns"""
        def handle_scorecard_not_found_error(scorecard):
            return {"success": False, "error": f"Scorecard not found: {scorecard}"}
        
        def handle_score_not_found_error(scorecard, score):
            return {"success": False, "error": f"Score not found in scorecard {scorecard}: {score}"}
        
        def handle_query_error(error):
            return {"success": False, "error": f"Scorecard query failed: {error}"}
        
        def handle_general_error(error):
            return {"success": False, "error": str(error)}
        
        # Test scorecard not found error
        error_result = handle_scorecard_not_found_error("nonexistent-scorecard")
        assert error_result['success'] is False
        assert "Scorecard not found: nonexistent-scorecard" in error_result['error']
        
        # Test score not found error
        error_result = handle_score_not_found_error("test-scorecard", "nonexistent-score")
        assert error_result['success'] is False
        assert "Score not found in scorecard test-scorecard: nonexistent-score" in error_result['error']
        
        # Test query error
        mock_error = Exception("GraphQL connection failed")
        error_result = handle_query_error(mock_error)
        assert error_result['success'] is False
        assert "Scorecard query failed: GraphQL connection failed" in error_result['error']
        
        # Test general error
        mock_error = RuntimeError("Unexpected system error")
        error_result = handle_general_error(mock_error)
        assert error_result['success'] is False
        assert "Unexpected system error" in error_result['error']


class TestCostAnalysisToolSharedPatterns:
    """Test shared patterns for cost analysis tools"""
    
    def test_client_dependency_patterns(self):
        """Test client and dependency import patterns"""
        def simulate_imports():
            # Mock successful imports
            imports = {
                'create_dashboard_client': lambda: 'mock_client',
                'resolve_account_id_for_command': lambda client, arg: 'account-123',
                'ScoreResultCostAnalyzer': lambda **kwargs: kwargs
            }
            return imports
        
        imports = simulate_imports()
        client = imports['create_dashboard_client']()
        account_id = imports['resolve_account_id_for_command'](client, None)
        analyzer_config = imports['ScoreResultCostAnalyzer'](
            client=client,
            account_id=account_id,
            days=1,
            hours=0
        )
        
        assert client == 'mock_client'
        assert account_id == 'account-123'
        assert analyzer_config['client'] == 'mock_client'
        assert analyzer_config['account_id'] == 'account-123'
    
    def test_graphql_query_patterns(self):
        """Test GraphQL query construction patterns"""
        def build_scorecard_name_query(scorecard_id):
            return f"""
            query GetScorecardName {{
              getScorecard(id: "{scorecard_id}") {{ id name }}
            }}
            """
        
        def build_scorecard_scores_query(scorecard_id):
            return f"""
            query GetScorecardForCostAnalysis {{
                getScorecard(id: "{scorecard_id}") {{
                    id
                    name
                    sections {{
                        items {{
                            scores {{
                                items {{
                                    id
                                    name
                                    key
                                    externalId
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """
        
        # Test scorecard name query
        name_query = build_scorecard_name_query("scorecard-123")
        assert f'getScorecard(id: "scorecard-123")' in name_query
        assert "GetScorecardName" in name_query
        assert "{ id name }" in name_query
        
        # Test scorecard scores query
        scores_query = build_scorecard_scores_query("scorecard-456")
        assert f'getScorecard(id: "scorecard-456")' in scores_query
        assert "GetScorecardForCostAnalysis" in scores_query
        assert "externalId" in scores_query
        assert "sections {" in scores_query
    
    def test_decimal_handling_patterns(self):
        """Test decimal handling for precise cost calculations"""
        def safe_decimal_conversion(value):
            try:
                return Decimal(value or "0")
            except Exception:
                return Decimal("0")
        
        # Test valid decimal values
        assert safe_decimal_conversion("0.001234") == Decimal("0.001234")
        # Note: float conversion has precision issues, so we test the string conversion approach
        assert str(safe_decimal_conversion(0.001234)).startswith("0.001234")
        assert safe_decimal_conversion("1.5") == Decimal("1.5")
        
        # Test invalid values default to zero
        assert safe_decimal_conversion(None) == Decimal("0")
        assert safe_decimal_conversion("") == Decimal("0")
        assert safe_decimal_conversion("invalid") == Decimal("0")
        
        # Test zero handling
        assert safe_decimal_conversion(0) == Decimal("0")
        assert safe_decimal_conversion("0") == Decimal("0")
    
    def test_defensive_data_access_patterns(self):
        """Test defensive data access patterns"""
        def safe_get_nested(data, *keys, default=None):
            """Safely get nested dictionary values"""
            current = data
            for key in keys:
                if isinstance(current, dict):
                    current = current.get(key)
                    if current is None:
                        return default
                else:
                    return default
            return current if current is not None else default
        
        def safe_get_items(data, default=None):
            """Safely get items list with defensive checks"""
            return (data.get('items', []) or []) if isinstance(data, dict) else (default or [])
        
        # Mock nested data structure
        mock_data = {
            'sections': {
                'items': [
                    {
                        'scores': {
                            'items': [
                                {'id': 'score-123', 'name': 'Test Score'}
                            ]
                        }
                    }
                ]
            }
        }
        
        # Test successful nested access
        sections = safe_get_nested(mock_data, 'sections', 'items')
        assert len(sections) == 1
        
        # Test failed nested access
        missing = safe_get_nested(mock_data, 'nonexistent', 'items')
        assert missing is None
        
        # Test safe items access
        items = safe_get_items(mock_data.get('sections', {}))
        assert len(items) == 1
        
        # Test safe items access with None
        items = safe_get_items(None, [])
        assert items == []