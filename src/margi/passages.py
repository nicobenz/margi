"""Trace literature quotes back into born-digital PDFs (pdfium only, no AI).

`finalize` locates every key passage of a `read` record: the page it is on, the paper's own
section path from the PDF outline, and one or two crop regions with the quoted lines to highlight.
The dashboard renders those regions to small page images in the gitignored cache.
"""

from __future__ import annotations

import hashlib
import re
import struct
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path

from .config import MARGI_DIR

CROPS = f"{MARGI_DIR}/.cache/lit/crops"
SCALE = 3          # render scale: 216 dpi, about 2x for a column shown at panel width
CONTEXT = 2        # lines of context above and below the quote
PAD = 6.0          # points around the crop
PAGE = [0.0, 0.0, 1.0, 1.0]  # a crop box covering the whole page (visual passages)

PUNCT = str.maketrans({"‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"', "„": '"',
                       "–": "-", "—": "-", "−": "-", "­": None})


def _fold(ch: str) -> str:
    return unicodedata.normalize("NFKC", ch).translate(PUNCT).casefold()


def normalize(text: str) -> str:
    """The comparison form of a quote: folded case, plain punctuation, single spaces, joined hyphens."""
    text = "".join(_fold(c) for c in text.replace("\x02", ""))
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"- ", "-", text).strip()


@dataclass
class Char:
    page: int
    index: int
    box: tuple[float, float, float, float] | None  # left, bottom, right, top in PDF points


Line = tuple[str, list[Char], bool]  # comparison text, source chars, ends hyphenated


def _page_lines(textpage, n: int) -> list[Line]:
    """The page's text lines in comparison form, each with the source char behind every character."""
    import pypdfium2.raw as raw

    lines: list[Line] = []
    out: list[str] = []
    src: list[Char] = []

    def close(hyphen: bool) -> None:
        nonlocal out, src
        while out and out[-1] == " ":
            out.pop()
            src.pop()
        if out:
            lines.append(("".join(out), src, hyphen or out[-1] == "-"))
        out, src = [], []

    for i in range(textpage.count_chars()):
        ch = chr(raw.FPDFText_GetUnicode(textpage.raw, i))
        if ch == "\x02":  # pdfium's mark for a word hyphenated at the line end
            close(True)
        elif ch in "\r\n":
            close(False)
        elif ch.isspace() or ch == "\x00":
            if out and out[-1] not in " -":  # as in normalize(): no space after a hyphen
                out.append(" ")
                src.append(Char(n, i, None))
        else:
            box = textpage.get_charbox(i)
            for f in _fold(ch):
                out.append(f)
                src.append(Char(n, i, box))
    close(False)
    return lines


def _furniture(pages: list[list[Line]]) -> list[set[int]]:
    """Per page, the indexes of running heads, footers and page numbers among its first and last lines."""
    sig = lambda text: re.sub(r"[\divxlc\s.]+$|^[\divxlc\s.]+|\d+", "", text)
    edges = [[i for i in (0, 1, len(ls) - 2, len(ls) - 1) if 0 <= i < len(ls)] for ls in pages]
    seen: dict[str, set[int]] = {}
    for n, ls in enumerate(pages):
        for i in set(edges[n]):
            if len(ls[i][0]) < 140 and sig(ls[i][0]):
                seen.setdefault(sig(ls[i][0]), set()).add(n)
    out = []
    for n, ls in enumerate(pages):
        drop = set()
        for i in set(edges[n]):
            text = ls[i][0]
            if re.fullmatch(r"[\divxlc\s.\-–]+", text) or len(seen.get(sig(text), ())) >= 2:
                drop.add(i)
        out.append(drop)
    return out


def _lines(chars: list[Char]) -> list[tuple[float, float, float, float]]:
    """Merge char boxes into line rectangles, breaking on a new baseline or a jump back in x."""
    lines: list[list[float]] = []
    last = None
    for c in chars:
        if not c.box or c.box[2] <= c.box[0]:
            continue
        l, b, r, t = c.box
        if last and abs((b + t) / 2 - (last[1] + last[3]) / 2) < max(t - b, last[3] - last[1]) * 0.6 and l >= last[0] - 2:
            cur = lines[-1]
            cur[0], cur[1], cur[2], cur[3] = min(cur[0], l), min(cur[1], b), max(cur[2], r), max(cur[3], t)
        else:
            lines.append([l, b, r, t])
        last = c.box
    return [tuple(x) for x in lines]


def _columns(rects: list[tuple]) -> list[list[tuple]]:
    """Split line rectangles where reading jumps back up the page (the next column), at most two."""
    groups: list[list[tuple]] = []
    for r in rects:
        if groups and r[3] <= groups[-1][-1][3] + 2:
            groups[-1].append(r)
        else:
            groups.append([r])
    return groups[:2]


def _sections(doc, textpages: dict) -> list[tuple[int, int, int, str]]:
    """Outline entries as (page, char index, level, title), placed in pdfium's reading order."""
    out = []
    for item in doc.get_toc():
        dest = item.get_dest()
        title = (item.get_title() or "").strip()
        if not dest or not title or dest.get_index() is None:
            continue
        page = dest.get_index()
        mode, view = dest.get_view()
        index = 0
        if view and len(view) >= 2 and page in textpages:
            index = _index_at(textpages[page], view[0], view[1])
        out.append((page, index, item.level, title))
    return sorted(out, key=lambda e: (e[0], e[1])) if len(out) >= 2 else []  # one entry is just the title


def _index_at(textpage, x: float, y: float) -> int:
    """The first char at or just below a destination point (headings sit right under it)."""
    best, best_d = 0, None
    for i in range(textpage.count_chars()):
        box = textpage.get_charbox(i)
        if box[2] <= box[0]:
            continue
        d = abs(box[0] - x) + max(0.0, box[3] - y - 3) * 4 + max(0.0, y - box[3])
        if best_d is None or d < best_d:
            best, best_d = i, d
    return best


def section_path(entries: list[tuple[int, int, int, str]], page: int, index: int, depth: int = 2) -> list[str]:
    stack: dict[int, str] = {}
    for p, i, level, title in entries:
        if (p, i) > (page, index):
            break
        stack = {k: v for k, v in stack.items() if k < level}
        stack[level] = title
    return [stack[k] for k in sorted(stack)][:depth]


def locate(pdf: Path, passages: list[dict]) -> list[dict]:
    """Anchor each `{page, quote, source}` passage in the PDF. Returns one anchor dict per passage."""
    import pypdfium2 as pdfium

    try:
        doc = pdfium.PdfDocument(pdf)
    except Exception:  # missing, encrypted or broken: nothing to check the quotes against
        return [{"status": "unchecked", "page": p.get("page")} for p in passages]
    try:
        pages, textpages, lines = [], {}, []
        for n in range(len(doc)):
            pages.append(doc[n])
            textpages[n] = pages[n].get_textpage()
            lines.append(_page_lines(textpages[n], n))
        drop = _furniture(lines)
        full, offsets, flat = "", [], []
        for n, page_lines in enumerate(lines):
            offsets.append(len(full))
            for i, (text, src, hyphen) in enumerate(page_lines):
                if i in drop[n]:
                    continue
                if hyphen and text.endswith("-") and _last_body(page_lines, drop[n]) == i:
                    text, src = text[:-1], src[:-1]  # a hyphen ending a page is a hyphenation
                full += text
                flat += src
                if not hyphen:
                    full += " "
                    flat.append(Char(-1, -1, None))
        entries = _sections(doc, textpages)
        labels = [_label(doc, n) for n in range(len(doc))]
        return [_anchor(p, full, offsets, flat, pages, entries, labels) for p in passages]
    finally:
        doc.close()


def _last_body(lines: list[Line], drop: set[int]) -> int:
    return max((i for i in range(len(lines)) if i not in drop), default=-1)


def _label(doc, n: int) -> str | None:
    """The page's printed number from the PDF's page labels ("233", "xii"), if the PDF has them."""
    try:
        label = doc.get_page_label(n)
    except Exception:
        return None
    return (label.strip() or None) if isinstance(label, str) else None


def _anchor(passage: dict, full: str, offsets: list[int], flat: list[Char], pages: list, entries: list,
            labels: list[str | None]) -> dict:
    stated = passage.get("page")
    if passage.get("source") == "visual":
        anchor = {"status": "visual", "page": stated}
        if isinstance(stated, int) and 1 <= stated <= len(pages) and labels[stated - 1]:
            anchor["label"] = labels[stated - 1]
        if isinstance(stated, int) and 1 <= stated <= len(pages) and pages[stated - 1].get_rotation() == 0:
            left, bottom, right, top = pages[stated - 1].get_cropbox()
            # the whole page, shown small: the student checks the quote on the image it was read from
            anchor.update(size=[round(right - left, 2), round(top - bottom, 2)], crops=[{"box": PAGE, "lines": []}])
        return anchor
    quote = normalize(str(passage.get("quote", "")))
    hits = [m.start() for m in re.finditer(re.escape(quote), full)] if len(quote) >= 8 else []
    if not hits:
        return {"status": "unresolved", "page": stated}
    page_of = lambda pos: max(i for i, o in enumerate(offsets) if o <= pos)
    on_page = [h for h in hits if isinstance(stated, int) and page_of(h) + 1 == stated]
    start = (on_page or hits)[0]
    first = page_of(start)
    chars = [c for c in flat[start:start + len(quote)] if c.page == first]
    page = pages[first]
    left, bottom, right, top = page.get_cropbox()
    width, height = right - left, top - bottom
    anchor = {"status": "ok" if on_page else "relocated", "page": first + 1,
              "size": [round(width, 2), round(height, 2)]}
    if labels[first]:
        anchor["label"] = labels[first]
    path = section_path(entries, first, chars[0].index if chars else 0)
    if path:
        anchor["section"] = path
    if page.get_rotation() == 0:
        anchor["crops"] = _crops(_lines(chars), flat, offsets[first], len(full) if first + 1 >= len(offsets)
                                 else offsets[first + 1], first, (left, bottom, width, height))
    return anchor


def _crops(match: list[tuple], flat: list[Char], lo: int, hi: int, page: int, frame: tuple) -> list[dict]:
    left, bottom, width, height = frame
    seen, page_chars = set(), []
    for c in flat[lo:hi]:
        if c.page == page and c.index not in seen:
            seen.add(c.index)
            page_chars.append(c)
    all_lines = _lines(page_chars)

    def frac(r: tuple) -> list[float]:  # PDF rect -> [x0, y0, x1, y1] as page fractions, origin top left
        return [round((r[0] - left) / width, 4), round((bottom + height - r[3]) / height, 4),
                round((r[2] - left) / width, 4), round((bottom + height - r[1]) / height, 4)]

    out = []
    for group in _columns(match):
        x0, x1 = min(r[0] for r in group), max(r[2] for r in group)
        y0, y1 = min(r[1] for r in group), max(r[3] for r in group)
        col = [r for r in all_lines if min(r[2], x1) - max(r[0], x0) > 0.5 * min(r[2] - r[0], x1 - x0)]
        reach = (CONTEXT + 1.5) * max(r[3] - r[1] for r in group) * 1.4  # context stays near the quote
        above = sorted((r for r in col if r[1] >= y1 - 1 and r[1] - y1 < reach), key=lambda r: r[1])
        below = sorted((r for r in col if r[3] <= y0 + 1 and y0 - r[3] < reach), key=lambda r: -r[3])
        box = group + above[:CONTEXT] + below[:CONTEXT]
        x0, x1 = min(r[0] for r in box), max(r[2] for r in box)
        y0, y1 = min(r[1] for r in box), max(r[3] for r in box)
        # stop halfway to the next line outside the crop, so no neighbouring line is sliced through
        top = (y1 + above[CONTEXT][1]) / 2 if len(above) > CONTEXT else y1 + PAD
        low = (y0 + below[CONTEXT][3]) / 2 if len(below) > CONTEXT else y0 - PAD
        crop = (max(left, x0 - PAD), max(bottom, max(low, y0 - PAD)),
                min(left + width, x1 + PAD), min(bottom + height, min(top, y1 + PAD)))
        out.append({"box": frac(crop), "lines": [frac(r) for r in group]})
    return out


# --------------------------------------------------------------------------- rendering


def crop_name(pdf_sha: str, page: int, box: list[float]) -> str:
    key = hashlib.sha256(f"{page}:{box}".encode()).hexdigest()[:10]
    return f"{pdf_sha[:16]}-p{page}-{key}.png"


def _png(width: int, height: int, stride: int, buf: bytes) -> bytes:
    rows = b"".join(b"\x00" + buf[y * stride:y * stride + width] for y in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def render(pdf: Path, jobs: list[tuple[int, list[float], Path]]) -> None:
    """Render `(page, box, out)` crops as greyscale PNGs. Boxes are page fractions, origin top left."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    try:
        for page_no, box, out in jobs:
            page = doc[page_no - 1]
            left, bottom, right, top = page.get_cropbox()
            w, h = right - left, top - bottom
            crop = (box[0] * w, (1 - box[3]) * h, (1 - box[2]) * w, box[1] * h)  # left, bottom, right, top margins
            # a whole page is shown as a small facsimile, so it needs far fewer pixels than an excerpt
            bitmap = page.render(scale=1 if box == PAGE else SCALE, crop=crop, grayscale=True)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(_png(bitmap.width, bitmap.height, bitmap.stride, bytes(bitmap.buffer)))
    finally:
        doc.close()


# --------------------------------------------------------------------------- records and dashboard


def trace(root: Path, payload: dict) -> dict:
    """Anchor the key passages of a `read` payload. margi writes every anchor; drafts can't supply one."""
    from .gitutil import sha256

    payload = dict(payload)
    ratings = []
    for item in payload.get("ratings") or []:
        if not isinstance(item, dict) or not item.get("pdf") or not item.get("key_passages"):
            ratings.append(item)
            continue
        item = dict(item)
        pdf = root / item["pdf"]
        passages = [dict(p) for p in item["key_passages"] if isinstance(p, dict)]
        for p in passages:
            p.pop("anchor", None)
        if pdf.is_file():
            item["pdf_sha256"] = sha256(pdf.read_bytes())
            anchors = locate(pdf, passages)
        else:  # nothing to check against: not the same as a quote that isn't in the paper
            anchors = [{"status": "unchecked", "page": p.get("page")} for p in passages]
        item["key_passages"] = [dict(p, anchor=a) for p, a in zip(passages, anchors)]
        ratings.append(item)
    payload["ratings"] = ratings
    return payload


def crop_jobs(root: Path, ratings: list[dict]) -> dict[Path, list[tuple[int, list[float], Path]]]:
    """Crops still to render, per PDF, for PDFs that are present and unchanged since they were read."""
    from .gitutil import sha256

    jobs: dict[Path, list] = {}
    for item in ratings:
        pdf, digest = root / item.get("pdf", ""), item.get("pdf_sha256")
        wanted = [(p["anchor"]["page"], c["box"], root / CROPS / crop_name(digest, p["anchor"]["page"], c["box"]))
                  for p in item.get("key_passages") or [] if digest
                  for c in (p.get("anchor") or {}).get("crops") or []]
        wanted = [j for j in wanted if not j[2].is_file()]
        if wanted and pdf.is_file() and sha256(pdf.read_bytes()) == digest:
            jobs[pdf] = wanted
    return jobs
