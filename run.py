#!/usr/bin/env python
"""
Async Web Automation & Telemetry Engine — Entry Script.

Convenience launcher delegating directly to main.cli.
Usage:
    py run.py --help
    py run.py <target_url_or_id>
    py run.py <target_url_or_id> --sync-session --concurrency 8
"""

import sys
from main import cli

if __name__ == "__main__":
    cli()
