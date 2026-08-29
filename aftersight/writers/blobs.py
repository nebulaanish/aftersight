"""Payloads too large to sit in the transcript spill to `blobs/` as plain text.

Plain `.txt` rather than escaped JSON, so a bare `rg` across the run directory
still finds what is in them.

`BlobWriter` is registered first in the writer chain: it normalises the payload
in place, so every later writer sees either `text` or `text_ref` + `preview` and
none of them has to think about size.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from aftersight import constants
from aftersight.events.schemas import Event


class BlobWriter:
    def __init__(self, run_dir: Path, max_bytes: int = 8192, preview_lines: int = 12):
        self.run_dir = Path(run_dir)
        self.max_bytes = max_bytes
        self.preview_lines = preview_lines

    def __call__(self, event: Event) -> None:
        text = event.payload.get("text")
        if not isinstance(text, str):
            return
        nbytes = len(text.encode())
        event.payload["bytes"] = nbytes
        if nbytes <= self.max_bytes:
            return
        digest = hashlib.sha1(text.encode()).hexdigest()[:8]
        blobs = self.run_dir / constants.BLOBS_DIR
        blobs.mkdir(parents=True, exist_ok=True)
        path = blobs / f"{digest}.txt"
        if not path.exists():
            path.write_text(text)
        del event.payload["text"]
        event.payload["text_ref"] = f"{constants.BLOBS_DIR}/{digest}.txt"
        event.payload["preview"] = "\n".join(text.split("\n")[: self.preview_lines])
