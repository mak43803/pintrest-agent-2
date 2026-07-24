"""
Job Store - Persistent storage for scheduled jobs.

Stores job metadata in SQLite so that scheduled tasks survive
application restarts.
"""

# TODO: Implement JobStore class
# - async save_job(job) -> persist job to database
# - async load_jobs() -> retrieve all active jobs
# - async update_job_status(job_id, status) -> update job state
# - async delete_job(job_id) -> remove job from store
