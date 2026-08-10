from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from loguru import logger

from .client import InfosysClient

COLLECTION_MIME = "application/vnd.ekstep.content-collection"

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ContentNode:
    """Represents a single learnable content unit (video, document, assessment, etc.)."""
    identifier:   str
    name:         str
    content_type: str
    mime_type:    str
    status:       str
    children:     List["ContentNode"] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return not self.children


def collect_leaves(node: ContentNode) -> List[ContentNode]:
    """Recursively collect all leaf nodes (actual content items to complete)."""
    if node.is_leaf:
        return [node]
    leaves: List[ContentNode] = []
    for child in node.children:
        leaves.extend(collect_leaves(child))
    return leaves


# ── Course reader ─────────────────────────────────────────────────────────────

class CourseReader:
    """Reads and parses the content hierarchy for a given Infosys Springboard course."""

    # Primary path — infosysheadstart hierarchy-service (confirmed working)
    HIERARCHY_PATH_PRIMARY = (
        "/api-gw/wn-apis/infosysheadstart/hierarchy-service/level/{id}/2"
    )
    # Fallback — Wingspan proxy content hierarchy
    HIERARCHY_PATH_FALLBACK = "/apis/proxies/v8/content/v3/hierarchy/{id}"

    def __init__(self, client: InfosysClient) -> None:
        self.client = client
        self._cache: dict = {}

    def fetch(self, course_id: str) -> Optional[ContentNode]:
        """
        Fetch full course content hierarchy by course identifier.
        Tries the infosysheadstart hierarchy-service first, then falls back
        to the Wingspan proxy hierarchy endpoint.
        """
        logger.info(f"Fetching course: {course_id}")

        root = self._fetch_node(course_id, depth=0)
        if not root:
            logger.error(
                f"Failed to fetch course '{course_id}'.\n"
                "  → Check the course ID is correct.\n"
                "  → Make sure you are enrolled in the course.\n"
                "  → Try re-running after refreshing your token."
            )
            return None

        leaves = collect_leaves(root)
        logger.success(
            f"Course '{root.name}' loaded — {len(leaves)} trackable content items."
        )
        return root

    def _fetch_node(self, node_id: str, depth: int = 0) -> Optional[ContentNode]:
        """Recursively fetch a node and its children."""
        if node_id in self._cache:
            return self._cache[node_id]

        resp = self._fetch_raw(node_id)
        if not resp:
            logger.warning(f"{'  ' * depth}Could not fetch node: {node_id}")
            return None

        name         = resp.get("name", node_id)
        mime_type    = resp.get("mimeType", "")
        content_type = resp.get("contentType", resp.get("category", ""))
        status       = resp.get("status", "Live")
        raw_children = resp.get("children", [])

        children_nodes: List[ContentNode] = []
        for raw in raw_children:
            cid   = raw.get("identifier", "")
            cmime = raw.get("mimeType", "")
            cname = raw.get("name", cid)
            ctype = raw.get("contentType", "")
            cstat = raw.get("status", "Live")

            if not cid:
                continue

            if cmime == COLLECTION_MIME:
                sub = self._fetch_node(cid, depth + 1)
                if sub:
                    children_nodes.append(sub)
                else:
                    children_nodes.append(ContentNode(
                        identifier=cid, name=cname, content_type=ctype,
                        mime_type=cmime, status=cstat,
                    ))
            else:
                children_nodes.append(ContentNode(
                    identifier=cid, name=cname, content_type=ctype,
                    mime_type=cmime, status=cstat,
                ))

        node = ContentNode(
            identifier=node_id,
            name=name,
            content_type=content_type,
            mime_type=mime_type,
            status=status,
            children=children_nodes,
        )
        self._cache[node_id] = node
        leaf_count = len(collect_leaves(node))
        logger.debug(f"{'  ' * depth}📁 {name[:60]} → {leaf_count} leaves")
        return node

    def _fetch_raw(self, node_id: str) -> Optional[dict]:
        """Try primary then fallback hierarchy endpoints."""
        # Primary: infosysheadstart hierarchy-service
        path = self.HIERARCHY_PATH_PRIMARY.format(id=node_id)
        resp = self.client.get(path, params={"sourceFields": "appIconLarge"})
        if resp:
            return resp

        # Fallback: Wingspan proxy content hierarchy
        path2 = self.HIERARCHY_PATH_FALLBACK.format(id=node_id)
        resp2 = self.client.get(path2)
        if resp2:
            # Proxy wraps data in result.content
            content = resp2.get("result", {}).get("content")
            if isinstance(content, dict):
                return content
            if isinstance(resp2, dict) and resp2.get("name"):
                return resp2

        return None

    def resolve_id_from_url(self, url: str) -> str:
        """
        Extracts the course identifier (lex_auth_XXXXX) from a Springboard URL.

        Handles:
          /web/en/app/toc/lex_auth_012345/overview
          /web/en/viewer/web-module/lex_auth_XXX?collectionId=lex_auth_YYY&...
        """
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        qs     = parse_qs(parsed.query)

        # Prefer collectionId query param (full learning-path ID)
        if "collectionId" in qs:
            return qs["collectionId"][0]

        parts = parsed.path.rstrip("/").split("/")
        for i, part in enumerate(parts):
            if part in ("toc", "viewer") and i + 1 < len(parts):
                candidate = parts[i + 1]
                if candidate.startswith("lex_"):
                    return candidate

        # Fallback: last lex_auth_* segment in the URL
        for part in reversed(parts):
            if part.startswith("lex_"):
                return part

        return parts[-1]
