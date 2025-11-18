#!/usr/bin/env python3
"""
Celery worker script for Kita
Usage: python celery_worker.py [worker|beat|flower]
"""
import os
import sys
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kita.settings')

def run_worker():
    """Run Celery worker"""
    cmd = [
        'celery', '-A', 'kita',
        'worker',
        '--loglevel=info',
        '--concurrency=2',
        '--queues=high,default,low',
        '--prefetch-multiplier=1'
    ]
    subprocess.run(cmd)

def run_beat():
    """Run Celery beat scheduler"""
    cmd = [
        'celery', '-A', 'kita',
        'beat',
        '--loglevel=info',
        '--schedule=/tmp/celerybeat-schedule'
    ]
    subprocess.run(cmd)

def run_flower():
    """Run Flower monitoring"""
    cmd = [
        'celery', '-A', 'kita',
        'flower',
        '--port=5555',
        f'--basic_auth={os.environ.get("FLOWER_BASIC_AUTH", "admin:admin")}'
    ]
    subprocess.run(cmd)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'worker':
            run_worker()
        elif command == 'beat':
            run_beat()
        elif command == 'flower':
            run_flower()
        else:
            print("Usage: python celery_worker.py [worker|beat|flower]")
    else:
        run_worker()