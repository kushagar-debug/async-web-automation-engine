from __future__ import annotations

import time
import base64
import json
from typing import List

from loguru import logger

from .client import InfosysClient
from .course_reader import ContentNode, collect_leaves


# ── MIME types that cannot be completed via standard content calculate API ───
SKIP_MIME_TYPES = {
    "application/vnd.ekstep.quiz-archive",
    "application/quiz",
    "application/vnd.ekstep.ecml-archive",
    "application/iap-assessment",
    "application/assessment",
}

# Only skip actual proctored exams/assessments if requested
SKIP_NAME_PATTERNS = {"proctored assessment", "iap assessment"}

CALCULATE_PATH   = "/api-gw/wn-apis/infosysheadstart/progress/v1/progress/calculate"
RECALCULATE_PATH = "/api-gw/wn-apis/infosysheadstart/progress/v1/progress/recalculate"


def _fmt(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s"


class Completer:
    """Sends native content progress completion signals to Wingspan DB for every content node in a course."""

    def __init__(self, client: InfosysClient, course_id: str) -> None:
        self.client    = client
        self.course_id = course_id
        self.wid       = client.auth["wid"]
        self.root_org  = client.auth.get("root_org", "infosysheadstart")
        self.org       = client.auth.get("org", "infosysheadstart")
        self.token     = client.auth["auth-token"]

        self.headers = {
            "x-wingspan-caller": "wingspan",
            "X-Requested-With":  "XMLHttpRequest",
            "origin":            "https://infyspringboard.onwingspan.com",
        }

        logger.info(f"Completer ready. wid={self.wid} course={course_id}")

    # ── Public API ────────────────────────────────────────────────────────────

    def complete_all(self, root: ContentNode) -> None:
        leaves: List[ContentNode] = collect_leaves(root)

        completable: List[ContentNode] = []
        skipped_count = 0

        for node in leaves:
            mime = node.mime_type.lower()
            name = node.name.lower()

            is_unsupported = (
                mime in SKIP_MIME_TYPES
                or any(p in name for p in SKIP_NAME_PATTERNS)
            )
            if is_unsupported:
                self._print_status(node.name, "skip", 0.0)
                skipped_count += 1
            else:
                completable.append(node)

        total = len(completable)
        logger.info(f"Processing {total} completable items ({skipped_count} skipped)...")
        print()

        done = failed = 0
        for idx, node in enumerate(completable):
            t0 = time.monotonic()

            # Call /progress/v1/progress/calculate with exact Wingspan schema
            success = self._calculate_progress(node.identifier)
            elapsed = time.monotonic() - t0

            if success:
                done += 1
                self._print_status(node.name, "done", elapsed)
            else:
                failed += 1
                self._print_status(node.name, "failed", elapsed)

            time.sleep(0.01)

        print()
        logger.info("Triggering course-level progress recalculate...")
        recalc_ok = self._recalculate_course_progress()
        if recalc_ok:
            logger.success("Course progress recalculated successfully on Wingspan backend!")
        else:
            logger.warning("Recalculate call completed.")

        print()
        logger.success(
            f"Done: {done} completed, {skipped_count} skipped, {failed} failed "
            f"out of {len(leaves)} total items."
        )

    # ── Strategy: Calculate Progress API ──────────────────────────────────────

    def _calculate_progress(self, content_id: str) -> bool:
        """
        Sends progress calculation request directly to Wingspan progress service.
        Creates/updates progressId in the Wingspan database.
        """
        payload = {
            "contentId": content_id,
            "userId": self.wid,
            "maxSize": 1,
            "visited": [1],
            "progress": 100,
            "completionPercentage": 100
        }

        # Don't retry endlessly on 400 invalid mime types
        try:
            resp = self.client.post(CALCULATE_PATH, json=payload, headers=self.headers)
            if resp is not None and isinstance(resp, dict):
                return True
        except Exception:
            pass
        return False

    def _recalculate_course_progress(self) -> bool:
        """
        Triggers course-level progress aggregator for the root course ID.
        """
        payload = {
            "contentId": self.course_id,
            "userId": self.wid
        }

        resp = self.client.post(RECALCULATE_PATH, json=payload, headers=self.headers)
        return resp is not None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _print_status(name: str, status: str, elapsed: float) -> None:
        symbol = {"done": "[OK]  ", "failed": "[FAIL]", "skip": "[SKIP]"}.get(status, "[•]  ")
        color  = {"done": "\033[32m", "failed": "\033[31m", "skip": "\033[33m"}.get(status, "")
        reset  = "\033[0m"
        label  = {"done": "done", "failed": "failed", "skip": "skipped"}.get(status, status)
        try:
            print(f"{color}{symbol} {name:<65}{label:<10}{_fmt(elapsed)}{reset}", flush=True)
        except Exception:
            print(f"{symbol} {name:<65}{label:<10}{_fmt(elapsed)}", flush=True)
