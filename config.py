#!/usr/bin/env python3
"""
Configuration management for the invoice processing workflow
"""

import os
from pathlib import Path

def load_env_file():
    """Load environment variables from .env file"""
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

def get_config():
    """Get configuration from environment variables"""
    # Load .env file first
    load_env_file()
    
    config = {
        'deepinfra_token': os.getenv('DEEPINFRA_TOKEN'),
        'tally_host': os.getenv('TALLY_HOST', 'localhost'),
        'tally_port': int(os.getenv('TALLY_PORT', '9000')),
        'company_name': os.getenv('COMPANY_NAME', 'Default Company')
    }
    
    return config

def validate_config():
    """Validate that required configuration is present"""
    config = get_config()
    
    if not config['deepinfra_token']:
        raise ValueError(
            "DEEPINFRA_TOKEN not found. Please:\n"
            "1. Set it in .env file, or\n"
            "2. Set environment variable: export DEEPINFRA_TOKEN=your_token"
        )
    
    return config