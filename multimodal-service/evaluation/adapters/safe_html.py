"""Extract inert DOM features from a local HTML string.

The original HTML is never returned.  Dangerous containers and event-bearing
attributes are ignored, and executable/data URLs are discarded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from evaluation.adapters.common import sanitize_inert_text

DANGEROUS_ELEMENTS = {"script", "style", "noscript", "iframe", "object", "embed", "template", "svg"}
SAFE_INPUT_ATTRS = ("type", "name", "id", "placeholder", "autocomplete")
UNSAFE_SCHEME = re.compile(r"^\s*(?:javascript|data|blob|vbscript)\s*:", re.IGNORECASE)
BASE64_LIKE = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")
MAX_TEXT_CHARS = 200_000
MAX_ITEMS = 2_000


def _clean_text(value: str | None, limit: int = 4_096) -> str:
    if not value:
        return ""
    value = sanitize_inert_text(BASE64_LIKE.sub("", value))
    return " ".join(value.split())[:limit]


def _safe_url(value: str | None) -> str | None:
    if not value or UNSAFE_SCHEME.match(value):
        return None
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    return cleaned


@dataclass
class ExtractedPage:
    title: str = ""
    visible_text: str = ""
    inputs: list[dict[str, Any]] = field(default_factory=list)
    forms: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)


class _FeatureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocked_depth = 0
        self.in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.forms: list[dict[str, Any]] = []
        self.form_stack: list[dict[str, Any]] = []
        self.inputs: list[dict[str, Any]] = []
        self.links: list[dict[str, Any]] = []
        self.link_stack: list[dict[str, Any]] = []
        self.label_stack: list[dict[str, Any]] = []
        self.labels_by_for: dict[str, str] = {}
        self.inputs_by_id: dict[str, dict[str, Any]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in DANGEROUS_ELEMENTS:
            self.blocked_depth += 1
            return
        if self.blocked_depth:
            return
        safe_attrs = {k.casefold(): v for k, v in attrs if not k.casefold().startswith("on")}
        if tag == "title":
            self.in_title = True
        elif tag == "form" and len(self.forms) < MAX_ITEMS:
            form = {
                "method": _clean_text(safe_attrs.get("method"), 32) or None,
                "action": _safe_url(safe_attrs.get("action")),
                "inputs": [],
            }
            self.forms.append(form)
            self.form_stack.append(form)
        elif tag == "input" and len(self.inputs) < MAX_ITEMS:
            item = {key: _clean_text(safe_attrs.get(key)) or None for key in SAFE_INPUT_ATTRS}
            item["label"] = None
            self.inputs.append(item)
            if self.form_stack:
                self.form_stack[-1]["inputs"].append(item)
            input_id = item.get("id")
            if input_id:
                self.inputs_by_id[input_id] = item
                if input_id in self.labels_by_for:
                    item["label"] = self.labels_by_for[input_id]
            if self.label_stack:
                self.label_stack[-1]["inputs"].append(item)
        elif tag == "a" and len(self.links) < MAX_ITEMS:
            link = {"text": "", "href": _safe_url(safe_attrs.get("href"))}
            self.links.append(link)
            self.link_stack.append(link)
        elif tag == "label":
            self.label_stack.append(
                {"for": _clean_text(safe_attrs.get("for")) or None, "parts": [], "inputs": []}
            )

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in DANGEROUS_ELEMENTS:
            if self.blocked_depth:
                self.blocked_depth -= 1
            return
        if self.blocked_depth:
            return
        if tag == "title":
            self.in_title = False
        elif tag == "form" and self.form_stack:
            self.form_stack.pop()
        elif tag == "a" and self.link_stack:
            self.link_stack.pop()
        elif tag == "label" and self.label_stack:
            context = self.label_stack.pop()
            label = _clean_text(" ".join(context["parts"]))
            if not label:
                return
            for item in context["inputs"]:
                if not item.get("label"):
                    item["label"] = label
            target_id = context["for"]
            if target_id:
                self.labels_by_for[target_id] = label
                target = self.inputs_by_id.get(target_id)
                if target and not target.get("label"):
                    target["label"] = label

    def handle_data(self, data: str) -> None:
        if self.blocked_depth:
            return
        cleaned = _clean_text(data)
        if not cleaned:
            return
        if self.in_title:
            self.title_parts.append(cleaned)
        else:
            self.text_parts.append(cleaned)
        if self.link_stack:
            current = self.link_stack[-1]
            current["text"] = _clean_text(f"{current['text']} {cleaned}")
        if self.label_stack:
            self.label_stack[-1]["parts"].append(cleaned)


def extract_features(html: str) -> ExtractedPage:
    parser = _FeatureParser()
    parser.feed(html)
    parser.close()
    return ExtractedPage(
        title=_clean_text(" ".join(parser.title_parts), 1_000),
        visible_text=_clean_text(" ".join(parser.text_parts), MAX_TEXT_CHARS),
        inputs=parser.inputs,
        forms=parser.forms,
        links=parser.links,
    )
