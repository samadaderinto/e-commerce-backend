"""Run without --preload; allocate a fresh multiprocess metrics dir per master."""
import os

bind = os.environ.get('GUNICORN_BIND', '127.0.0.1:8000')
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
timeout = 30
accesslog = None  # Request summaries are emitted as JSON by Django middleware.
errorlog = '-'


def on_starting(server):
    directory = os.environ.get('PROMETHEUS_MULTIPROC_DIR')
    if not directory or not os.path.isdir(directory):
        raise RuntimeError('Create and export a fresh PROMETHEUS_MULTIPROC_DIR before starting Gunicorn.')


def child_exit(server, worker):
    from prometheus_client import multiprocess
    multiprocess.mark_process_dead(worker.pid)
