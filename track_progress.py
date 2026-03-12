import time
import os
import subprocess
import re

LOG_FILE = "/Users/ryan.porter/.cursor/projects/Users-ryan-porter-Projects-Plexus/terminals/854872.txt"
KBS_ISSUE = "31806e"

def update_kbs(comment):
    print(f"Updating KBS: {comment}")
    subprocess.run(["kbs", "comment", KBS_ISSUE, comment], cwd="/Users/ryan.porter/Projects/Plexus")

def main():
    update_kbs("Started background tracker to monitor report generation progress.")
    subprocess.run(["kbs", "update", KBS_ISSUE, "--status", "in_progress"], cwd="/Users/ryan.porter/Projects/Plexus")
    
    last_pos = 0
    current_report = None
    completed_reports = []
    
    # Quick catch-up without posting every single one individually if they already passed
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            last_pos = len(content)
            
            # Find all completed reports so far
            creates = re.findall(r"Creating Report DB record: '(.*?)'", content)
            completed_reports.extend(creates[:-1] if len(creates) > 1 else [])
            if creates:
                current_report = creates[-1]
                
    if current_report:
        update_kbs(f"Currently processing: **{current_report}**\n\nAlready completed: {len(completed_reports)}")
    
    while True:
        time.sleep(60)
        
        if not os.path.exists(LOG_FILE):
            continue
            
        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(last_pos)
            new_data = f.read()
            last_pos = f.tell()
            
            if not new_data:
                continue
                
            creates = re.findall(r"Creating Report DB record: '(.*?)'", new_data)
            successes = re.findall(r"Report completed successfully!", new_data)
            
            for create in creates:
                current_report = create
                update_kbs(f"Started generating: **{current_report}**")
                
            for success in successes:
                if current_report:
                    update_kbs(f"✅ Successfully completed: **{current_report}**")
                    completed_reports.append(current_report)
                    current_report = None
                    
            # Check if script ended
            if "ended_at:" in new_data:
                update_kbs("🎉 All background report generation tasks have completed!")
                subprocess.run(["kbs", "update", KBS_ISSUE, "--status", "done"], cwd="/Users/ryan.porter/Projects/Plexus")
                break

if __name__ == "__main__":
    main()
