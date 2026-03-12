import re
with open('plexus/reports/blocks/vector_topic_memory.py', 'r') as f:
    code = f.read()

# I will use a Python script to do AST or regex based replacement, 
# but it's simpler to just write the new file completely since I know what it should do.
