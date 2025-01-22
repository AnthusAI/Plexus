import pytest
from plexus.cli.TaskTargeting import TaskTargetPattern, TaskTargetMatcher

def test_task_target_pattern_validation():
    # Valid patterns
    TaskTargetPattern("domain/subdomain")
    TaskTargetPattern("*/subdomain")
    TaskTargetPattern("domain/*")
    TaskTargetPattern("*/*")
    TaskTargetPattern("*")
    TaskTargetPattern("[domain1,domain2]/subdomain")
    
    # Invalid patterns
    with pytest.raises(ValueError):
        TaskTargetPattern("")
    
    with pytest.raises(ValueError):
        TaskTargetPattern("invalid")
        
    with pytest.raises(ValueError):
        TaskTargetPattern("domain/subdomain/extra")
        
    with pytest.raises(ValueError):
        TaskTargetPattern("invalid@domain/subdomain")
        
    with pytest.raises(ValueError):
        TaskTargetPattern("domain/invalid@subdomain")
        
    with pytest.raises(ValueError):
        TaskTargetPattern("[]/subdomain")
        
    with pytest.raises(ValueError):
        TaskTargetPattern("[domain1,,domain2]/subdomain")

def test_task_target_pattern_matching():
    # Exact matches
    pattern = TaskTargetPattern("domain/subdomain")
    assert pattern.matches("domain/subdomain")
    assert not pattern.matches("other/subdomain")
    assert not pattern.matches("domain/other")
    assert not pattern.matches("invalid")
    
    # Wildcard domain
    pattern = TaskTargetPattern("*/subdomain")
    assert pattern.matches("domain/subdomain")
    assert pattern.matches("other/subdomain")
    assert not pattern.matches("domain/other")
    
    # Wildcard subdomain
    pattern = TaskTargetPattern("domain/*")
    assert pattern.matches("domain/subdomain")
    assert pattern.matches("domain/other")
    assert not pattern.matches("other/subdomain")
    
    # Full wildcard
    pattern = TaskTargetPattern("*/*")
    assert pattern.matches("domain/subdomain")
    assert pattern.matches("other/other")
    
    # Global wildcard
    pattern = TaskTargetPattern("*")
    assert pattern.matches("domain/subdomain")
    assert pattern.matches("other/other")
    
    # Domain list
    pattern = TaskTargetPattern("[domain1,domain2]/subdomain")
    assert pattern.matches("domain1/subdomain")
    assert pattern.matches("domain2/subdomain")
    assert not pattern.matches("domain3/subdomain")
    assert not pattern.matches("domain1/other")

def test_task_target_matcher():
    # Single pattern
    matcher = TaskTargetMatcher(["domain/subdomain"])
    assert matcher.matches("domain/subdomain")
    assert not matcher.matches("other/subdomain")
    
    # Multiple patterns
    matcher = TaskTargetMatcher([
        "domain1/subdomain1",
        "domain2/*",
        "*/subdomain3"
    ])
    assert matcher.matches("domain1/subdomain1")
    assert matcher.matches("domain2/anything")
    assert matcher.matches("anything/subdomain3")
    assert not matcher.matches("domain1/subdomain2")
    
    # Domain list pattern
    matcher = TaskTargetMatcher([
        "[domain1,domain2]/subdomain",
        "domain3/*"
    ])
    assert matcher.matches("domain1/subdomain")
    assert matcher.matches("domain2/subdomain")
    assert matcher.matches("domain3/anything")
    assert not matcher.matches("domain4/subdomain")

def test_target_validation():
    assert TaskTargetMatcher.validate_target("domain/subdomain")
    assert not TaskTargetMatcher.validate_target("")
    assert not TaskTargetMatcher.validate_target("invalid")
    assert not TaskTargetMatcher.validate_target("invalid@/subdomain")
    assert not TaskTargetMatcher.validate_target("domain/invalid@") 