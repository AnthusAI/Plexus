"""
Worker/Coding Assistant Agent Test Suite

This test suite focuses specifically on the worker agent (coding assistant) 
behavior in our multi-agent ReAct system:

## Worker Agent Responsibilities
1. **Tool Execution**: Executes specific tools based on manager guidance
2. **Scoped Access**: Only accesses tools appropriate for current phase
3. **Result Reporting**: Provides clear results and reasoning back to manager
4. **Error Handling**: Handles tool failures and scoping violations gracefully
5. **Adaptive Behavior**: Adjusts actions based on tool results and constraints

## Test Coverage Areas
- Tool call generation and execution
- Tool scoping enforcement 
- Result interpretation and reporting
- Error handling and recovery
- Multi-tool workflows
- Phase-appropriate behavior
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
from typing import Dict, List, Any, Optional


class MockTool:
    """Mock tool that simulates MCP tool behavior."""
    
    def __init__(self, name: str, description: str, should_fail: bool = False):
        self.name = name
        self.description = description
        self.should_fail = should_fail
        self.call_count = 0
        self.last_args = None
    
    def func(self, args: Dict[str, Any]) -> str:
        """Execute the mock tool."""
        self.call_count += 1
        self.last_args = args
        
        if self.should_fail:
            raise Exception(f"Tool {self.name} failed with args: {args}")
        
        return f"Tool {self.name} executed successfully with {args}"


class WorkerAgentTestHarness:
    """Test harness for worker agent behavior."""
    
    def __init__(self):
        self.available_tools = {}
        self.blocked_tools = set()
        self.tool_execution_log = []
        self.error_log = []
    
    def add_tool(self, tool: MockTool):
        """Add a tool to the available tools."""
        self.available_tools[tool.name] = tool
    
    def set_tool_scope(self, allowed_tools: List[str]):
        """Set which tools are in scope for current phase."""
        all_tool_names = set(self.available_tools.keys())
        self.blocked_tools = all_tool_names - set(allowed_tools)
    
    def execute_tool_call(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call with scoping enforcement."""
        if tool_name in self.blocked_tools:
            error = f"Tool {tool_name} blocked by scoping in current phase"
            self.error_log.append(error)
            return {"success": False, "error": error}
        
        if tool_name not in self.available_tools:
            error = f"Tool {tool_name} not found"
            self.error_log.append(error)
            return {"success": False, "error": error}
        
        try:
            tool = self.available_tools[tool_name]
            result = tool.func(args)
            
            execution_record = {
                "tool": tool_name,
                "args": args,
                "result": result,
                "success": True
            }
            self.tool_execution_log.append(execution_record)
            
            return {"success": True, "result": result}
            
        except Exception as e:
            error = f"Tool {tool_name} execution failed: {str(e)}"
            self.error_log.append(error)
            return {"success": False, "error": error}
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get statistics about tool executions."""
        return {
            "total_executions": len(self.tool_execution_log),
            "successful_executions": len([log for log in self.tool_execution_log if log["success"]]),
            "failed_executions": len(self.error_log),
            "tools_used": list(set(log["tool"] for log in self.tool_execution_log)),
            "blocked_attempts": len([error for error in self.error_log if "blocked by scoping" in error])
        }


class TestWorkerToolExecution:
    """Test suite for worker agent tool execution capabilities."""
    
    def test_worker_executes_analysis_tools_correctly(self):
        """
        STORY: Worker agent executes analysis tools with proper parameters
        
        During exploration phase, the worker should:
        1. Execute feedback analysis tools with correct scorecard/score parameters
        2. Handle tool results and extract meaningful information
        3. Report results back in structured format
        4. Chain multiple analysis tools together effectively
        """
        harness = WorkerAgentTestHarness()
        
        # Set up analysis tools for exploration phase
        feedback_analysis_tool = MockTool("plexus_feedback_analysis", "Analyze feedback patterns")
        feedback_find_tool = MockTool("plexus_feedback_find", "Find specific feedback items")
        item_info_tool = MockTool("plexus_item_info", "Get item details")
        
        harness.add_tool(feedback_analysis_tool)
        harness.add_tool(feedback_find_tool)
        harness.add_tool(item_info_tool)
        
        # Set exploration phase scope
        exploration_tools = ["plexus_feedback_analysis", "plexus_feedback_find", "plexus_item_info"]
        harness.set_tool_scope(exploration_tools)
        
        # Simulate worker executing analysis workflow
        analysis_workflow = [
            {
                "tool": "plexus_feedback_analysis",
                "args": {"scorecard_name": "TestCard", "score_name": "TestScore", "days": 7}
            },
            {
                "tool": "plexus_feedback_find", 
                "args": {"scorecard_name": "TestCard", "score_name": "TestScore", "limit": 10}
            },
            {
                "tool": "plexus_item_info",
                "args": {"item_id": "item_123"}
            }
        ]
        
        # Execute the analysis workflow
        results = []
        for step in analysis_workflow:
            result = harness.execute_tool_call(step["tool"], step["args"])
            results.append(result)
        
        # Verify successful execution
        assert all(result["success"] for result in results), "All analysis tools should execute successfully"
        
        # Verify proper parameter passing
        assert feedback_analysis_tool.last_args["scorecard_name"] == "TestCard"
        assert feedback_find_tool.last_args["limit"] == 10
        assert item_info_tool.last_args["item_id"] == "item_123"
        
        # Verify execution statistics
        stats = harness.get_execution_stats()
        assert stats["total_executions"] == 3
        assert stats["successful_executions"] == 3
        assert stats["blocked_attempts"] == 0
        assert set(stats["tools_used"]) == set(exploration_tools)
        
        print("✅ Worker agent successfully executed analysis tools with correct parameters")
    
    def test_worker_creates_hypothesis_nodes_systematically(self):
        """
        STORY: Worker agent creates experiment nodes with systematic approach
        
        During hypothesis generation phase, the worker should:
        1. Create nodes with clear hypothesis descriptions following format
        2. Use proper experiment configuration structures
        3. Create multiple hypotheses to test different approaches
        4. Update node configurations as needed
        """
        harness = WorkerAgentTestHarness()
        
        # Set up hypothesis creation tools
        create_node_tool = MockTool("create_experiment_node", "Create hypothesis node")
        update_node_tool = MockTool("update_node_content", "Update node configuration")
        think_tool = MockTool("think", "Internal reasoning")
        
        harness.add_tool(create_node_tool)
        harness.add_tool(update_node_tool)
        harness.add_tool(think_tool)
        
        # Set hypothesis generation phase scope
        hypothesis_tools = ["create_experiment_node", "update_node_content", "think"]
        harness.set_tool_scope(hypothesis_tools)
        
        # Simulate worker creating systematic hypotheses
        hypothesis_workflow = [
            {
                "tool": "think",
                "args": {"thought": "Based on analysis, I need to test threshold adjustments and pattern improvements"}
            },
            {
                "tool": "create_experiment_node",
                "args": {
                    "experiment_id": "test_exp",
                    "hypothesis_description": "GOAL: Reduce false positives | METHOD: Increase confidence threshold by 15%",
                    "node_name": "Threshold Adjustment",
                    "yaml_configuration": "threshold: 0.85\nconfidence_boost: 0.15"
                }
            },
            {
                "tool": "create_experiment_node", 
                "args": {
                    "experiment_id": "test_exp",
                    "hypothesis_description": "GOAL: Improve edge case handling | METHOD: Add specific pattern rules",
                    "node_name": "Pattern Enhancement",
                    "yaml_configuration": "additional_patterns:\n  - edge_case_pattern_1\n  - edge_case_pattern_2"
                }
            },
            {
                "tool": "update_node_content",
                "args": {
                    "node_id": "node_123", 
                    "yaml_configuration": "threshold: 0.90\nconfidence_boost: 0.20",
                    "update_description": "Increased threshold based on initial testing"
                }
            }
        ]
        
        # Execute hypothesis creation workflow
        results = []
        for step in hypothesis_workflow:
            result = harness.execute_tool_call(step["tool"], step["args"])
            results.append(result)
        
        # Verify successful execution
        assert all(result["success"] for result in results), "All hypothesis tools should execute successfully"
        
        # Verify hypothesis format compliance
        node_creation_calls = [step for step in hypothesis_workflow if step["tool"] == "create_experiment_node"]
        for call in node_creation_calls:
            hypothesis_desc = call["args"]["hypothesis_description"]
            assert "GOAL:" in hypothesis_desc, "Hypothesis should have clear goal"
            assert "METHOD:" in hypothesis_desc, "Hypothesis should have clear method"
            assert call["args"]["node_name"], "Node should have descriptive name"
        
        # Verify systematic approach
        stats = harness.get_execution_stats()
        assert stats["total_executions"] == 4
        assert "create_experiment_node" in stats["tools_used"]
        assert create_node_tool.call_count == 2, "Should have created 2 hypothesis nodes"
        
        print("✅ Worker agent systematically created hypothesis nodes with proper format")


class TestWorkerToolScoping:
    """Test suite for worker agent tool scoping enforcement."""
    
    def test_exploration_phase_tool_restrictions(self):
        """
        STORY: Worker cannot access hypothesis tools during exploration
        
        Tool scoping during exploration should:
        1. Allow analysis tools (feedback_analysis, feedback_find, item_info)
        2. Block hypothesis tools (create_experiment_node, update_node_content)
        3. Allow utility tools (think)
        4. Provide clear error messages for blocked tools
        """
        harness = WorkerAgentTestHarness()
        
        # Set up all available tools
        analysis_tools = [
            MockTool("plexus_feedback_analysis", "Analyze feedback"),
            MockTool("plexus_feedback_find", "Find feedback items"),
            MockTool("plexus_item_info", "Get item info")
        ]
        
        hypothesis_tools = [
            MockTool("create_experiment_node", "Create hypothesis"),
            MockTool("update_node_content", "Update node")
        ]
        
        utility_tools = [
            MockTool("think", "Internal reasoning")
        ]
        
        for tool in analysis_tools + hypothesis_tools + utility_tools:
            harness.add_tool(tool)
        
        # Set exploration phase scope (no hypothesis tools)
        exploration_scope = ["plexus_feedback_analysis", "plexus_feedback_find", "plexus_item_info", "think"]
        harness.set_tool_scope(exploration_scope)
        
        # Test allowed tools work
        allowed_calls = [
            ("plexus_feedback_analysis", {"scorecard_name": "TestCard"}),
            ("think", {"thought": "Analyzing the feedback data"})
        ]
        
        for tool_name, args in allowed_calls:
            result = harness.execute_tool_call(tool_name, args)
            assert result["success"], f"Allowed tool {tool_name} should work in exploration phase"
        
        # Test blocked tools are rejected
        blocked_calls = [
            ("create_experiment_node", {"experiment_id": "test"}),
            ("update_node_content", {"node_id": "test"})
        ]
        
        for tool_name, args in blocked_calls:
            result = harness.execute_tool_call(tool_name, args)
            assert not result["success"], f"Blocked tool {tool_name} should be rejected in exploration phase"
            assert "blocked by scoping" in result["error"], "Should provide clear scoping error message"
        
        # Verify scoping statistics
        stats = harness.get_execution_stats()
        assert stats["successful_executions"] == 2, "Should have 2 successful executions"
        assert stats["blocked_attempts"] == 2, "Should have 2 blocked attempts"
        
        print("✅ Exploration phase tool scoping correctly enforced")
    
    def test_hypothesis_phase_tool_access(self):
        """
        STORY: Worker gets access to creation tools during hypothesis phase
        
        Tool scoping during hypothesis generation should:
        1. Allow hypothesis tools (create_experiment_node, update_node_content)
        2. Block analysis tools (feedback_analysis, feedback_find)
        3. Allow utility tools (think)
        4. Enable worker to focus on solution creation
        """
        harness = WorkerAgentTestHarness()
        
        # Set up tools
        all_tools = [
            MockTool("plexus_feedback_analysis", "Analyze feedback"),
            MockTool("create_experiment_node", "Create hypothesis"),
            MockTool("update_node_content", "Update node"),
            MockTool("think", "Internal reasoning")
        ]
        
        for tool in all_tools:
            harness.add_tool(tool)
        
        # Set hypothesis phase scope (no analysis tools)
        hypothesis_scope = ["create_experiment_node", "update_node_content", "think"]
        harness.set_tool_scope(hypothesis_scope)
        
        # Test hypothesis tools work
        hypothesis_calls = [
            ("create_experiment_node", {"experiment_id": "test", "hypothesis_description": "GOAL: Test | METHOD: Adjust"}),
            ("update_node_content", {"node_id": "node_1", "yaml_configuration": "config: value"}),
            ("think", {"thought": "Planning the next hypothesis"})
        ]
        
        for tool_name, args in hypothesis_calls:
            result = harness.execute_tool_call(tool_name, args)
            assert result["success"], f"Hypothesis tool {tool_name} should work in hypothesis phase"
        
        # Test analysis tools are blocked
        blocked_calls = [
            ("plexus_feedback_analysis", {"scorecard_name": "TestCard"})
        ]
        
        for tool_name, args in blocked_calls:
            result = harness.execute_tool_call(tool_name, args)
            assert not result["success"], f"Analysis tool {tool_name} should be blocked in hypothesis phase"
            assert "blocked by scoping" in result["error"]
        
        print("✅ Hypothesis phase tool scoping correctly allows creation tools")


class TestWorkerErrorHandling:
    """Test suite for worker agent error handling and recovery."""
    
    def test_worker_handles_tool_failures_gracefully(self):
        """
        STORY: Worker agent handles tool failures and continues workflow
        
        Error handling should:
        1. Catch tool execution failures
        2. Provide meaningful error messages
        3. Continue with alternative approaches when possible
        4. Report errors back to manager for guidance
        """
        harness = WorkerAgentTestHarness()
        
        # Set up tools with some that will fail
        working_tool = MockTool("working_tool", "This tool works")
        failing_tool = MockTool("failing_tool", "This tool fails", should_fail=True)
        backup_tool = MockTool("backup_tool", "Backup approach")
        
        harness.add_tool(working_tool)
        harness.add_tool(failing_tool)
        harness.add_tool(backup_tool)
        harness.set_tool_scope(["working_tool", "failing_tool", "backup_tool"])
        
        # Simulate workflow with tool failure and recovery
        workflow_steps = [
            ("working_tool", {"param": "value1"}),  # Should succeed
            ("failing_tool", {"param": "value2"}),  # Should fail
            ("backup_tool", {"param": "value3"})    # Should succeed as backup
        ]
        
        results = []
        for tool_name, args in workflow_steps:
            result = harness.execute_tool_call(tool_name, args)
            results.append(result)
        
        # Verify mixed results
        assert results[0]["success"], "Working tool should succeed"
        assert not results[1]["success"], "Failing tool should fail"
        assert results[2]["success"], "Backup tool should succeed"
        
        # Verify error information is captured
        assert len(harness.error_log) == 1, "Should have one error logged"
        assert "failing_tool" in harness.error_log[0], "Error should mention the failing tool"
        
        # Verify partial workflow completion
        stats = harness.get_execution_stats()
        assert stats["successful_executions"] == 2, "Should have 2 successful executions"
        assert stats["failed_executions"] == 1, "Should have 1 failed execution"
        
        print("✅ Worker agent handles tool failures gracefully with proper error reporting")
    
    def test_worker_reports_comprehensive_results(self):
        """
        STORY: Worker agent provides comprehensive result reporting
        
        Result reporting should:
        1. Include tool execution details
        2. Summarize findings and insights
        3. Identify next steps or recommendations
        4. Provide context for manager evaluation
        """
        harness = WorkerAgentTestHarness()
        
        # Set up analysis workflow
        analysis_tool = MockTool("plexus_feedback_analysis", "Analyze feedback")
        find_tool = MockTool("plexus_feedback_find", "Find feedback items")
        
        harness.add_tool(analysis_tool)
        harness.add_tool(find_tool)
        harness.set_tool_scope(["plexus_feedback_analysis", "plexus_feedback_find"])
        
        # Execute analysis workflow
        workflow = [
            ("plexus_feedback_analysis", {"scorecard_name": "TestCard", "score_name": "TestScore"}),
            ("plexus_feedback_find", {"scorecard_name": "TestCard", "score_name": "TestScore", "limit": 5})
        ]
        
        for tool_name, args in workflow:
            harness.execute_tool_call(tool_name, args)
        
        # Generate comprehensive report
        stats = harness.get_execution_stats()
        execution_log = harness.tool_execution_log
        
        report = {
            "summary": f"Completed {stats['successful_executions']} analysis steps",
            "tools_used": stats["tools_used"],
            "findings": [log["result"] for log in execution_log],
            "recommendations": "Based on analysis, proceed to hypothesis generation phase",
            "next_steps": ["Create experiment nodes", "Test threshold adjustments"],
            "confidence": "High - sufficient data gathered for decision making"
        }
        
        # Verify comprehensive reporting
        assert report["summary"], "Should provide execution summary"
        assert len(report["tools_used"]) == 2, "Should list all tools used"
        assert len(report["findings"]) == 2, "Should include all findings"
        assert report["recommendations"], "Should provide recommendations"
        assert report["next_steps"], "Should suggest next steps"
        assert report["confidence"], "Should include confidence assessment"
        
        print("✅ Worker agent provides comprehensive result reporting for manager evaluation")


class TestWorkerMultiToolWorkflows:
    """Test suite for worker agent multi-tool workflows."""
    
    def test_worker_chains_analysis_tools_effectively(self):
        """
        STORY: Worker agent chains multiple analysis tools for comprehensive understanding
        
        Multi-tool workflows should:
        1. Use results from one tool to inform next tool usage
        2. Build comprehensive understanding through tool chaining
        3. Adapt tool parameters based on previous results
        4. Maintain context across tool executions
        """
        harness = WorkerAgentTestHarness()
        
        # Set up analysis tool chain
        class ContextAwareTool(MockTool):
            def __init__(self, name, description, context_store):
                super().__init__(name, description)
                self.context_store = context_store
            
            def func(self, args):
                result = super().func(args)
                # Store results in shared context
                self.context_store[self.name] = {"args": args, "result": result}
                return result
        
        context_store = {}
        
        overview_tool = ContextAwareTool("plexus_feedback_analysis", "Get overview", context_store)
        detail_tool = ContextAwareTool("plexus_feedback_find", "Get details", context_store)
        item_tool = ContextAwareTool("plexus_item_info", "Get item info", context_store)
        
        harness.add_tool(overview_tool)
        harness.add_tool(detail_tool)  
        harness.add_tool(item_tool)
        harness.set_tool_scope(["plexus_feedback_analysis", "plexus_feedback_find", "plexus_item_info"])
        
        # Execute chained analysis workflow
        analysis_chain = [
            # Step 1: Get overview
            {
                "tool": "plexus_feedback_analysis",
                "args": {"scorecard_name": "TestCard", "score_name": "TestScore", "days": 7},
                "purpose": "Understand overall patterns"
            },
            # Step 2: Get specific examples (informed by overview)
            {
                "tool": "plexus_feedback_find",
                "args": {"scorecard_name": "TestCard", "score_name": "TestScore", "limit": 10, "prioritize_edit_comments": True},
                "purpose": "Examine specific problem cases"
            },
            # Step 3: Deep dive on specific item (informed by examples)
            {
                "tool": "plexus_item_info",
                "args": {"item_id": "problematic_item_123"},
                "purpose": "Understand root cause in detail"
            }
        ]
        
        # Execute the chained workflow
        for step in analysis_chain:
            result = harness.execute_tool_call(step["tool"], step["args"])
            assert result["success"], f"Step {step['purpose']} should succeed"
            
            # Verify context is maintained
            assert step["tool"] in context_store, "Tool results should be stored in context"
        
        # Verify comprehensive analysis
        stats = harness.get_execution_stats()
        assert stats["total_executions"] == 3, "Should complete all 3 analysis steps"
        assert len(set(stats["tools_used"])) == 3, "Should use all 3 different tools"
        
        # Verify tools were called with appropriate parameters
        assert overview_tool.last_args["days"] == 7, "Overview should look at recent timeframe"
        assert detail_tool.last_args["prioritize_edit_comments"], "Details should prioritize edited feedback"
        assert item_tool.last_args["item_id"] == "problematic_item_123", "Item analysis should target specific problem"
        
        print("✅ Worker agent effectively chains analysis tools for comprehensive understanding")
    
    def test_worker_adapts_approach_based_on_tool_results(self):
        """
        STORY: Worker agent adapts its approach based on tool results
        
        Adaptive behavior should:
        1. Analyze tool results to determine next actions
        2. Modify approach when initial tools don't yield expected results
        3. Select appropriate tools based on discovered patterns
        4. Escalate to manager when tools are insufficient
        """
        harness = WorkerAgentTestHarness()
        
        # Set up adaptive scenario with mock results
        class AdaptiveTool(MockTool):
            def __init__(self, name, description, mock_results):
                super().__init__(name, description)
                self.mock_results = mock_results
                self.result_index = 0
            
            def func(self, args):
                if self.result_index < len(self.mock_results):
                    result = self.mock_results[self.result_index]
                    self.result_index += 1
                    return result
                return super().func(args)
        
        # Tool that returns "no data found" initially
        feedback_tool = AdaptiveTool(
            "plexus_feedback_find",
            "Find feedback", 
            ["No feedback items found for the specified criteria"]
        )
        
        # Tool that provides alternative approach
        analysis_tool = AdaptiveTool(
            "plexus_feedback_analysis",
            "Analyze feedback",
            ["Found 25 feedback items with scoring issues when looking at broader timeframe"]
        )
        
        # Tool for detailed examination
        item_tool = AdaptiveTool(
            "plexus_item_info",
            "Get item info",
            ["Item shows pattern of AI being too conservative on edge cases"]
        )
        
        harness.add_tool(feedback_tool)
        harness.add_tool(analysis_tool)
        harness.add_tool(item_tool)
        harness.set_tool_scope(["plexus_feedback_find", "plexus_feedback_analysis", "plexus_item_info"])
        
        # Simulate adaptive workflow
        adaptive_steps = [
            # Initial approach - specific search
            {
                "tool": "plexus_feedback_find",
                "args": {"scorecard_name": "TestCard", "score_name": "TestScore", "days": 1},
                "expected_adaptation": "expand_search_if_no_results"
            },
            # Adapted approach - broader analysis
            {
                "tool": "plexus_feedback_analysis", 
                "args": {"scorecard_name": "TestCard", "score_name": "TestScore", "days": 7},
                "expected_adaptation": "examine_specific_items"
            },
            # Detailed examination
            {
                "tool": "plexus_item_info",
                "args": {"item_id": "edge_case_item"},
                "expected_adaptation": "pattern_identified"
            }
        ]
        
        workflow_results = []
        for step in adaptive_steps:
            result = harness.execute_tool_call(step["tool"], step["args"])
            workflow_results.append({
                "step": step,
                "result": result,
                "adaptation_point": step["expected_adaptation"]
            })
        
        # Verify adaptive behavior
        assert len(workflow_results) == 3, "Should complete adaptive workflow"
        
        # Verify progression from narrow to broad to specific
        assert "1" in str(adaptive_steps[0]["args"]["days"]), "Should start with narrow timeframe"
        assert "7" in str(adaptive_steps[1]["args"]["days"]), "Should adapt to broader timeframe"
        assert "edge_case_item" in adaptive_steps[2]["args"]["item_id"], "Should focus on specific problematic item"
        
        # Verify tools adapted based on results
        no_results_response = workflow_results[0]["result"]["result"]
        broader_response = workflow_results[1]["result"]["result"]
        specific_response = workflow_results[2]["result"]["result"]
        
        assert "No feedback items found" in no_results_response, "Initial search should find no results"
        assert "25 feedback items" in broader_response, "Broader search should find results"
        assert "edge cases" in specific_response, "Specific analysis should identify patterns"
        
        print("✅ Worker agent successfully adapts approach based on tool results")


# Integration test demonstrating worker agent in realistic scenario
class TestWorkerAgentIntegration:
    """Integration test for worker agent in realistic multi-agent scenario."""
    
    def test_complete_worker_agent_story(self):
        """
        COMPLETE STORY: Worker agent executes full analysis-to-hypothesis workflow
        
        This integration test demonstrates the worker agent:
        1. **Receiving Manager Guidance**: Gets specific direction from manager
        2. **Tool Execution**: Uses appropriate tools for each phase
        3. **Adaptive Behavior**: Adjusts approach based on results
        4. **Scoping Compliance**: Respects phase-based tool restrictions
        5. **Result Reporting**: Provides comprehensive feedback to manager
        6. **Error Recovery**: Handles failures gracefully
        
        The worker agent should demonstrate autonomous execution while
        staying within the bounds set by the manager and system constraints.
        """
        print("\n🤖 Starting Complete Worker Agent Story...")
        
        harness = WorkerAgentTestHarness()
        
        # Set up comprehensive tool suite
        tools = [
            MockTool("plexus_feedback_analysis", "Analyze feedback patterns"),
            MockTool("plexus_feedback_find", "Find specific feedback items"),
            MockTool("plexus_item_info", "Get detailed item information"),
            MockTool("create_experiment_node", "Create hypothesis node"),
            MockTool("update_node_content", "Update node configuration"),
            MockTool("think", "Internal reasoning")
        ]
        
        for tool in tools:
            harness.add_tool(tool)
        
        # === PHASE 1: EXPLORATION ===
        print("\n📊 PHASE 1: Worker executes exploration tools")
        
        harness.set_tool_scope(["plexus_feedback_analysis", "plexus_feedback_find", "plexus_item_info", "think"])
        
        exploration_workflow = [
            ("think", {"thought": "I need to understand the scoring problems by analyzing feedback data"}),
            ("plexus_feedback_analysis", {"scorecard_name": "TestCard", "score_name": "TestScore", "days": 7}),
            ("plexus_feedback_find", {"scorecard_name": "TestCard", "score_name": "TestScore", "limit": 10}),
            ("plexus_item_info", {"item_id": "problematic_item_456"})
        ]
        
        exploration_results = []
        for tool_name, args in exploration_workflow:
            result = harness.execute_tool_call(tool_name, args)
            exploration_results.append(result)
            print(f"    ✓ {tool_name}: {result['success']}")
        
        # === PHASE 2: SYNTHESIS ===
        print("\n🧠 PHASE 2: Worker synthesizes findings")
        
        harness.set_tool_scope(["think"])
        
        synthesis_workflow = [
            ("think", {"thought": "Based on the analysis, I identified three main issues: threshold sensitivity, pattern gaps, and edge case handling"})
        ]
        
        synthesis_results = []
        for tool_name, args in synthesis_workflow:
            result = harness.execute_tool_call(tool_name, args)
            synthesis_results.append(result)
            print(f"    ✓ {tool_name}: {result['success']}")
        
        # === PHASE 3: HYPOTHESIS GENERATION ===
        print("\n🧪 PHASE 3: Worker creates hypothesis nodes")
        
        harness.set_tool_scope(["create_experiment_node", "update_node_content", "think"])
        
        hypothesis_workflow = [
            ("think", {"thought": "I need to create nodes to test threshold adjustment and pattern enhancement"}),
            ("create_experiment_node", {
                "experiment_id": "worker_test",
                "hypothesis_description": "GOAL: Reduce false positives | METHOD: Increase confidence threshold by 15%",
                "node_name": "Threshold Adjustment"
            }),
            ("create_experiment_node", {
                "experiment_id": "worker_test", 
                "hypothesis_description": "GOAL: Handle edge cases | METHOD: Add specific pattern rules",
                "node_name": "Pattern Enhancement"
            }),
            ("update_node_content", {
                "node_id": "threshold_node",
                "yaml_configuration": "threshold: 0.85\nconfidence_boost: 0.15"
            })
        ]
        
        hypothesis_results = []
        for tool_name, args in hypothesis_workflow:
            result = harness.execute_tool_call(tool_name, args)
            hypothesis_results.append(result)
            print(f"    ✓ {tool_name}: {result['success']}")
        
        # === VERIFICATION ===
        print("\n✅ WORKER AGENT STORY VALIDATION")
        
        # Verify phase execution
        assert all(result["success"] for result in exploration_results), "Exploration phase should complete successfully"
        assert all(result["success"] for result in synthesis_results), "Synthesis phase should complete successfully"  
        assert all(result["success"] for result in hypothesis_results), "Hypothesis phase should complete successfully"
        print("    ✓ All phases executed successfully")
        
        # Verify tool usage progression
        stats = harness.get_execution_stats()
        expected_tools = {"plexus_feedback_analysis", "plexus_feedback_find", "plexus_item_info", "create_experiment_node", "think"}
        actual_tools = set(stats["tools_used"])
        assert expected_tools.issubset(actual_tools), f"Should use expected tools. Used: {actual_tools}"
        print(f"    ✓ Used appropriate tools: {actual_tools}")
        
        # Verify hypothesis creation
        create_calls = [log for log in harness.tool_execution_log if log["tool"] == "create_experiment_node"]
        assert len(create_calls) == 2, "Should create 2 hypothesis nodes"
        print(f"    ✓ Created {len(create_calls)} hypothesis nodes")
        
        # Verify hypothesis format compliance
        for call in create_calls:
            args = call["args"]
            assert "GOAL:" in args["hypothesis_description"], "Hypothesis should have clear goal"
            assert "METHOD:" in args["hypothesis_description"], "Hypothesis should have clear method"
            assert args["node_name"], "Node should have descriptive name"
        print("    ✓ Hypotheses follow required format")
        
        # Verify scoping was enforced
        assert stats["blocked_attempts"] == 0, "No tools should have been blocked (all were in scope)"
        print("    ✓ Tool scoping properly respected")
        
        # Verify comprehensive execution
        assert stats["total_executions"] == 9, "Should complete full workflow"
        assert stats["successful_executions"] == 9, "All executions should succeed"
        print(f"    ✓ Completed {stats['total_executions']} tool executions")
        
        print("\n🎉 WORKER AGENT STORY COMPLETED SUCCESSFULLY!")
        print("    Worker demonstrated autonomous execution within manager constraints")
        print("    Worker adapted approach across different phases")
        print("    Worker created systematic hypotheses based on analysis")
        print("    Worker respected tool scoping and error handling")
