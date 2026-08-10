#!/usr/bin/env python
"""
run.py — Convenience entry point for Infosys Springboard automation.

Usage:
    py run.py <course_url_or_id>
    py run.py <course_url_or_id> --skip-verify

Examples:
    py run.py "https://infyspringboard.onwingspan.com/web/en/app/toc/lex_auth_012345/overview"
    py run.py lex_auth_012345678901234567890_shared
"""
import sys
from infosys.main import main

if __name__ == "__main__":
    main(standalone_mode=True)
