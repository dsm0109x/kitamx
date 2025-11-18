"""Flower configuration file - credentials from environment variables"""
import os

# Server configuration
address = '127.0.0.1'
port = 5555

# Authentication - read from environment variables
basic_auth = [f"{os.environ.get('FLOWER_BASIC_AUTH_USER', 'admin')}:{os.environ.get('FLOWER_BASIC_AUTH_PASS', 'changeme')}"]

# Broker URL from environment (SSL verification enabled by default)
broker_api = os.environ.get('VALKEY_URL', 'redis://localhost:6379/0')
