"""
Demonstration of the Output Aliasing Bug That Was Fixed

This script shows exactly what was happening before your co-worker's fix,
where classification values were incorrectly being placed in explanation fields
due to the output aliasing logic preserving existing values when it shouldn't.
"""

def simulate_old_buggy_behavior():
    """Simulate the OLD buggy output aliasing behavior"""
    
    class MockState:
        def __init__(self):
            # This simulates the state after a node has run
            self.classification = "NA"  # Node classified as NA
            self.explanation = "Customer only wants cosmetic changes"  # Node's detailed explanation
            self.value = "NA"  # Node's output aliasing set this
            self.text = "I just want to change the style"
            
        def model_dump(self):
            return {attr: getattr(self, attr) for attr in dir(self) 
                   if not attr.startswith('_') and not callable(getattr(self, attr))}
    
    def old_buggy_aliasing_function(state, output_mapping):
        """This is the OLD buggy logic that was causing problems"""
        new_state = state.model_dump()
        
        for alias, original in output_mapping.items():
            # OLD BUGGY LOGIC: Check if target field already has a value
            current_alias_value = getattr(state, alias, None)
            if current_alias_value is not None and current_alias_value != "":
                print(f"  🐛 SKIPPING alias {alias} because it already has value: {current_alias_value!r}")
                continue  # Skip this alias - preserve the existing value
            
            if hasattr(state, original):
                original_value = getattr(state, original)
                if original_value is not None:
                    new_state[alias] = original_value
                    print(f"  ✓ Setting {alias} = {original_value!r} (from {original})")
                else:
                    # Apply default for None values
                    if alias == "value":
                        new_state[alias] = "No"
                    else:
                        new_state[alias] = ""
                    print(f"  ⚠ Setting {alias} = {new_state[alias]!r} (default for None)")
            else:
                # Treat as literal value
                new_state[alias] = original
                print(f"  📝 Setting {alias} = {original!r} (literal)")
        
        # Convert back to object
        result = MockState()
        for key, value in new_state.items():
            setattr(result, key, value)
        return result
    
    # Test scenario: Final output aliasing maps value->classification, explanation->explanation
    output_mapping = {"value": "classification", "explanation": "explanation"}
    
    print("🔍 DEMONSTRATING THE OLD BUG")
    print("=" * 50)
    
    state = MockState()
    print(f"BEFORE aliasing:")
    print(f"  state.value = {getattr(state, 'value', 'NOT_SET')!r}")
    print(f"  state.explanation = {getattr(state, 'explanation', 'NOT_SET')!r}")
    print(f"  state.classification = {getattr(state, 'classification', 'NOT_SET')!r}")
    print()
    
    print("OLD BUGGY ALIASING PROCESS:")
    result = old_buggy_aliasing_function(state, output_mapping)
    print()
    
    print(f"AFTER old buggy aliasing:")
    print(f"  result.value = {getattr(result, 'value', 'NOT_SET')!r}")
    print(f"  result.explanation = {getattr(result, 'explanation', 'NOT_SET')!r}")
    print(f"  result.classification = {getattr(result, 'classification', 'NOT_SET')!r}")
    print()
    
    print("🚨 THE PROBLEM:")
    print(f"   - The 'value' field was supposed to get the classification ('NA')")
    print(f"   - But it was SKIPPED because 'value' already had 'NA'")
    print(f"   - The 'explanation' field was supposed to stay as the detailed explanation")
    print(f"   - But it was SKIPPED because 'explanation' already had a value")
    print(f"   - Result: Final output aliasing didn't work properly!")


def simulate_new_fixed_behavior():
    """Simulate the NEW fixed output aliasing behavior"""
    
    class MockState:
        def __init__(self):
            self.classification = "NA"
            self.explanation = "Customer only wants cosmetic changes"
            self.value = "NA"
            self.text = "I just want to change the style"
            
        def model_dump(self):
            return {attr: getattr(self, attr) for attr in dir(self) 
                   if not attr.startswith('_') and not callable(getattr(self, attr))}
    
    def new_fixed_aliasing_function(state, output_mapping):
        """This is the NEW fixed logic"""
        new_state = state.model_dump()
        
        for alias, original in output_mapping.items():
            # NEW FIXED LOGIC: Always apply the aliasing, no checking for existing values
            if hasattr(state, original):
                original_value = getattr(state, original)
                if original_value is not None:
                    new_state[alias] = original_value
                    print(f"  ✓ Setting {alias} = {original_value!r} (from {original})")
                else:
                    # Apply default for None values
                    if alias == "value":
                        new_state[alias] = "No"
                    else:
                        new_state[alias] = ""
                    print(f"  ⚠ Setting {alias} = {new_state[alias]!r} (default for None)")
            else:
                # Treat as literal value
                new_state[alias] = original
                print(f"  📝 Setting {alias} = {original!r} (literal)")
        
        # Convert back to object
        result = MockState()
        for key, value in new_state.items():
            setattr(result, key, value)
        return result
    
    output_mapping = {"value": "classification", "explanation": "explanation"}
    
    print("\n✅ DEMONSTRATING THE NEW FIX")
    print("=" * 50)
    
    state = MockState()
    print(f"BEFORE aliasing:")
    print(f"  state.value = {getattr(state, 'value', 'NOT_SET')!r}")
    print(f"  state.explanation = {getattr(state, 'explanation', 'NOT_SET')!r}")
    print(f"  state.classification = {getattr(state, 'classification', 'NOT_SET')!r}")
    print()
    
    print("NEW FIXED ALIASING PROCESS:")
    result = new_fixed_aliasing_function(state, output_mapping)
    print()
    
    print(f"AFTER new fixed aliasing:")
    print(f"  result.value = {getattr(result, 'value', 'NOT_SET')!r}")
    print(f"  result.explanation = {getattr(result, 'explanation', 'NOT_SET')!r}")
    print(f"  result.classification = {getattr(result, 'classification', 'NOT_SET')!r}")
    print()
    
    print("🎉 THE FIX:")
    print(f"   - The 'value' field gets the classification ('NA') as intended")
    print(f"   - The 'explanation' field keeps the detailed explanation as intended")
    print(f"   - Final output aliasing works correctly!")


if __name__ == "__main__":
    simulate_old_buggy_behavior()
    simulate_new_fixed_behavior()
    
    print("\n" + "=" * 60)
    print("SUMMARY: What your co-worker fixed")
    print("=" * 60)
    print("❌ OLD BUG: Output aliasing would skip fields that already had values")
    print("✅ NEW FIX: Output aliasing always applies, ensuring correct final mapping")
    print("🎯 IMPACT: Final output fields now get the correct values from the intended sources")