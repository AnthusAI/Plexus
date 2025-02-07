from api import DB, AnthusScorecardJob

def query_job(job_id):
    with DB.get_session() as session:
        job = session.query(AnthusScorecardJob).filter_by(job_id=job_id).first()
        print(f'Job found: {job is not None}')
        if job:
            # Convert job details to a readable format
            details = {k: str(v) for k, v in job.__dict__.items() if not k.startswith('_')}
            print('Job details:')
            for key, value in details.items():
                print(f'  {key}: {value}')
        else:
            print('No job found with this ID')

if __name__ == '__main__':
    job_id = 'e40969b9-3e1b-4209-976d-71bb2906e93e'
    query_job(job_id) 