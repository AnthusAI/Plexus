"""
SERIOUS BUG SCENARIO: Classification value going into explanation field

This demonstrates a more serious case where the old bug would cause 
classification values to end up in explanation fields, creating confusing
and incorrect outputs.
"""

def demonstrate_serious_bug_scenario():
    """Show a scenario where the bug causes really confusing output"""
    
    class MockState:
        def __init__(self):
            # Imagine a node that classifies something as "Reject" with a detailed explanation
            self.classification = "Reject"  # Node classified as Reject
            self.explanation = "Application lacks required documentation and has incomplete financial statements"
            # But through some earlier processing, these fields got set:
            self.value = "Pass"  # Some earlier step set this incorrectly
            self.reason = "Reject"  # Some earlier step set this
            
        def model_dump(self):
            return {attr: getattr(self, attr) for attr in dir(self) 
                   if not attr.startswith('_') and not callable(getattr(self, attr))}
    
    def old_buggy_aliasing_function(state, output_mapping):
        """OLD buggy logic that preserves existing values"""
        new_state = state.model_dump()
        
        for alias, original in output_mapping.items():
            current_alias_value = getattr(state, alias, None)
            if current_alias_value is not None and current_alias_value != "":
                print(f"  🐛 SKIPPING {alias} (preserving existing: {current_alias_value!r})")
                continue
            
            if hasattr(state, original):
                original_value = getattr(state, original)
                new_state[alias] = original_value
                print(f"  ✓ Setting {alias} = {original_value!r}")
        
        result = MockState()
        for key, value in new_state.items():
            setattr(result, key, value)
        return result
    
    def new_fixed_aliasing_function(state, output_mapping):
        """NEW fixed logic that always applies aliasing"""
        new_state = state.model_dump()
        
        for alias, original in output_mapping.items():
            if hasattr(state, original):
                original_value = getattr(state, original)
                new_state[alias] = original_value
                print(f"  ✓ Setting {alias} = {original_value!r} (from {original})")
        
        result = MockState()
        for key, value in new_state.items():
            setattr(result, key, value)
        return result
    
    # Final output mapping that should map the correct values to final fields
    output_mapping = {
        "value": "classification",      # Final result should be the classification
        "explanation": "explanation"    # Final explanation should be the detailed explanation
    }
    
    print("💥 SERIOUS BUG SCENARIO")
    print("=" * 60)
    print("Scenario: Application review system with final output mapping")
    print()
    
    state = MockState()
    print("INITIAL STATE (after node processing):")
    print(f"  classification = {state.classification!r}  ← Correct decision")
    print(f"  explanation = {state.explanation!r}")
    print(f"  value = {state.value!r}  ← Wrong value from earlier step") 
    print(f"  reason = {state.reason!r}")
    print()
    
    print("🐛 WITH OLD BUGGY BEHAVIOR:")
    old_result = old_buggy_aliasing_function(state, output_mapping)
    print()
    print("FINAL OUTPUT (what user sees):")
    print(f"  ❌ DECISION: {old_result.value!r}  ← WRONG! Should be 'Reject'")
    print(f"  ❌ EXPLANATION: {old_result.explanation!r}")
    print("  ^^ User sees 'Pass' decision with explanation about rejection - CONFUSING!")
    print()
    
    print("✅ WITH NEW FIXED BEHAVIOR:")
    new_result = new_fixed_aliasing_function(state, output_mapping)
    print()
    print("FINAL OUTPUT (what user sees):")
    print(f"  ✅ DECISION: {new_result.value!r}  ← CORRECT!")
    print(f"  ✅ EXPLANATION: {new_result.explanation!r}")
    print("  ^^ User sees consistent 'Reject' decision with proper explanation - CLEAR!")


def demonstrate_another_scenario():
    """Another scenario where values end up in wrong fields"""
    
    class MockState:
        def __init__(self):
            # A classification node that determines risk level
            self.classification = "High Risk"
            self.explanation = "Multiple red flags detected in transaction pattern"
            # But some condition or edge earlier set these:
            self.final_decision = "Low Risk"  # Wrong from earlier step
            self.justification = "High Risk"  # Partial value from earlier
            
        def model_dump(self):
            return {attr: getattr(self, attr) for attr in dir(self) 
                   if not attr.startswith('_') and not callable(getattr(self, attr))}
    
    def old_buggy_aliasing(state, mapping):
        """Preserves existing values - causes problems"""
        new_state = state.model_dump()
        for alias, original in mapping.items():
            current = getattr(state, alias, None)
            if current is not None and current != "":
                continue  # Skip - preserve existing
            new_state[alias] = getattr(state, original)
        
        result = MockState()
        for k, v in new_state.items():
            setattr(result, k, v)
        return result
    
    def new_fixed_aliasing(state, mapping):
        """Always applies correct mapping"""
        new_state = state.model_dump()
        for alias, original in mapping.items():
            new_state[alias] = getattr(state, original)
        
        result = MockState()
        for k, v in new_state.items():
            setattr(result, k, v)
        return result
    
    output_mapping = {
        "final_decision": "classification",
        "justification": "explanation"
    }
    
    print("\n" + "=" * 60)
    print("ANOTHER SERIOUS SCENARIO: Risk Assessment System")
    print("=" * 60)
    
    state = MockState()
    print("AFTER RISK ANALYSIS:")
    print(f"  classification = {state.classification!r}")
    print(f"  explanation = {state.explanation!r}")
    print(f"  final_decision = {state.final_decision!r}  ← Wrong from earlier")
    print(f"  justification = {state.justification!r}  ← Partial from earlier")
    print()
    
    old_result = old_buggy_aliasing(state, output_mapping)
    print("🐛 OLD BUG RESULT:")
    print(f"  final_decision = {old_result.final_decision!r}  ← DANGEROUS! Wrong risk level")
    print(f"  justification = {old_result.justification!r}  ← CONFUSING! Classification in justification")
    print()
    
    new_result = new_fixed_aliasing(state, output_mapping)
    print("✅ NEW FIXED RESULT:")
    print(f"  final_decision = {new_result.final_decision!r}  ← CORRECT! Proper risk level")
    print(f"  justification = {new_result.justification!r}")
    print("  ^^ Proper explanation for the decision")


if __name__ == "__main__":
    demonstrate_serious_bug_scenario()
    demonstrate_another_scenario()
    
    print("\n" + "🎯 " + "=" * 58)
    print("BOTTOM LINE: What your co-worker fixed")
    print("=" * 60)
    print("The old logic would preserve existing field values instead of")
    print("applying the final output mapping, causing:")
    print()
    print("❌ Classification values ending up in wrong fields")
    print("❌ Inconsistent decision/explanation pairs")
    print("❌ Confusing outputs where values don't match")
    print("❌ Potentially dangerous misclassifications in production")
    print()
    print("✅ The fix ensures final output mapping ALWAYS applies")
    print("✅ Fields get the correct values from intended sources")
    print("✅ Consistent, predictable output mapping behavior")