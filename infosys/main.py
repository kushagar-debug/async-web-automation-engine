from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import click
from loguru import logger

from .client import InfosysClient
from .completer import Completer
from .course_reader import CourseReader


BANNER = r"""
  _____        __                          _         
 |_   _|      / _|                        (_)        
   | |  _ __ | |_ ___  ___ _   _ ___      _ ___     
   | | | '_ \|  _/ _ \/ __| | | / __|    | / __|    
  _| |_| | | | || (_) \__ \ |_| \__ \    | \__ \    
 |_____|_| |_|_| \___/|___/\__, |___/    |_|___/    
                             __/ |                   
                            |___/  Springboard Auto  
"""


@click.command()
@click.argument("course")
@click.option(
    "--skip-verify",
    is_flag=True,
    default=False,
    help="Skip authentication verification step.",
)
def main(course: str, skip_verify: bool) -> None:
    """
    Automatically complete an Infosys Springboard course.

    COURSE can be:
      - A full course URL:  https://infyspringboard.onwingspan.com/.../toc/lex_auth_XXX/...
      - A bare course ID:   lex_auth_012345678901234567890
    """
    click.echo(BANNER)

    # ── Initialise client ─────────────────────────────────────────────────────
    try:
        client = InfosysClient()
    except SystemExit:
        raise

    # ── Auth check ────────────────────────────────────────────────────────────
    if not skip_verify:
        if not client.verify_auth():
            logger.error(
                "Authentication failed. Update auth-token and wid in "
                "~/.infosys-course/config.json and retry."
            )
            raise SystemExit(1)

    # ── Resolve course ID from URL if needed ──────────────────────────────────
    reader = CourseReader(client)
    if course.startswith("http"):
        course_id = reader.resolve_id_from_url(course)
        logger.info(f"Resolved course ID from URL: {course_id}")
    else:
        course_id = course

    # ── Fetch course hierarchy ────────────────────────────────────────────────
    root = reader.fetch(course_id)
    if root is None:
        logger.error("Could not fetch course content. Check the course ID and your enrollment.")
        raise SystemExit(1)

    # ── Complete all items ────────────────────────────────────────────────────
    completer = Completer(client, course_id)
    completer.complete_all(root)


if __name__ == "__main__":
    main()
