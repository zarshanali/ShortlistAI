"""Turn ANY resume file into plain text.

Supported (detected from the file's first bytes, so a wrongly named file still works):
  PDF            pypdf, then `pdftotext`, then OCR if the PDF is a scan (needs tesseract)
  DOCX           read straight from the XML - also gets text boxes, tables, headers
  DOC (old Word) antiword / catdoc / LibreOffice if installed, else a best-effort fallback
  RTF, ODT, HTML, TXT, MD, LOG, CSV
  PNG / JPG / TIFF / BMP images of a CV (OCR, needs tesseract)
  ZIP            expanded into the files inside it (see expand_zip)
Nothing is ever written to your disk except short-lived temp files for converters.
"""
from __future__ import annotations

import html as _html
import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import List, Tuple

from .config import MAX_FILE_MB, MAX_ZIP_TOTAL_MB

MAX_CHARS = 200_000
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
TEXT_EXT = {".txt", ".md", ".log", ".csv", ".text", ".json"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


class ReadError(Exception):
    """A file that cannot be read - the message is shown to the user."""


@dataclass
class Read:
    text: str
    kind: str
    warning: str = ""


# ------------------------------------------------------------------ detection
def sniff(name: str, data: bytes) -> str:
    ext = os.path.splitext(name.lower())[1]
    head = data[:2048]
    if data[:5] == b"%PDF-" or b"%PDF-" in head[:1024]:
        return "pdf"
    if data[:2] == b"PK":
        try:
            names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
        except zipfile.BadZipFile:
            raise ReadError("The file is damaged (not a valid ZIP/DOCX).")
        if "word/document.xml" in names:
            return "docx"
        if "content.xml" in names and "META-INF/manifest.xml" in names:
            return "odt"
        if any(n.startswith(("xl/", "ppt/")) for n in names):
            raise ReadError("Excel/PowerPoint files are not resumes. Save the CV as PDF or DOCX.")
        return "zip"
    if data[:8] == OLE_MAGIC:
        if ext in (".xls", ".ppt"):
            raise ReadError("Excel/PowerPoint files are not resumes. Save the CV as PDF or DOCX.")
        return "doc"
    if data[:5] == b"{\\rtf":
        return "rtf"
    low = head.lower().lstrip()
    if low.startswith((b"<!doctype html", b"<html", b"<?xml")) or ext in (".html", ".htm"):
        return "html"
    if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff" or data[:4] in (b"II*\x00", b"MM\x00*") or data[:2] == b"BM":
        return "image"
    if ext in IMAGE_EXT:
        return "image"
    if ext in TEXT_EXT or _mostly_text(head):
        return "text"
    raise ReadError(f"Unsupported file type '{ext or 'unknown'}'. Use PDF, DOCX, DOC, RTF, ODT, TXT, HTML or an image.")


def _mostly_text(b: bytes) -> bool:
    if not b:
        return False
    printable = sum(1 for x in b if x in (9, 10, 13) or 32 <= x < 127 or x >= 160)
    return printable / len(b) > 0.9 and b"\x00" not in b


def decode_bytes(b: bytes) -> str:
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return b.decode("utf-16", errors="ignore")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1", errors="ignore")


def _tidy(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_CHARS]


# ------------------------------------------------------------------ each format
def _pdf(data: bytes, ocr: bool) -> Tuple[str, str]:
    text, warn = "", ""
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                unlocked = bool(reader.decrypt(""))          # 0 = wrong password
            except Exception:
                unlocked = False
            if not unlocked:
                raise ReadError("The PDF is password protected.")
        parts = []
        for page in reader.pages[:25]:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(parts)
    except ReadError:
        raise
    except Exception:
        text = ""
    if len(text.strip()) < 40 and shutil.which("pdftotext"):
        text = _run_tool(["pdftotext", "-layout", "-l", "25", "{in}", "-"], data, ".pdf") or text
    if len(text.strip()) < 40:
        if ocr and shutil.which("tesseract") and shutil.which("pdftoppm"):
            text = _ocr_pdf(data)
            warn = ("Scanned PDF - text read with OCR (check it looks right)." if len(text.strip()) >= 40
                    else "No text could be read, even with OCR.")
        else:
            warn = "No text found - probably a scanned/image PDF. Install tesseract (OCR) or send a text-based PDF."
    return text, warn


def _wxml_to_text(xml: str) -> str:
    xml = re.sub(r"<mc:Fallback>.*?</mc:Fallback>", "", xml, flags=re.S)      # Word stores text boxes twice
    out = []
    for m in re.finditer(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>|(</w:p>)|(<w:tab\s*/>)|(<w:br[^>]*/>)|(<w:cr\s*/>)|(</w:tc>)", xml):
        if m.group(1) is not None:
            out.append(_html.unescape(m.group(1)))
        elif m.group(2) or m.group(4) or m.group(5):
            out.append("\n")
        else:
            out.append("\t")
    return "".join(out)


def _docx(data: bytes) -> str:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ReadError("The DOCX file is damaged.")
    names = z.namelist()
    ordered = sorted(n for n in names if re.match(r"word/header\d*\.xml$", n)) + ["word/document.xml"] + \
        sorted(n for n in names if re.match(r"word/footer\d*\.xml$", n))
    return "\n".join(_wxml_to_text(z.read(n).decode("utf-8", "ignore")) for n in ordered if n in names)


def _odt(data: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(data))
    xml = z.read("content.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</text:(?:p|h)>|<text:line-break\s*/>", "\n", xml)
    xml = re.sub(r"<text:tab\s*/>", "\t", xml)
    return _html.unescape(re.sub(r"<[^>]+>", "", xml))


class _Strip(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "ul", "ol", "table"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)


def _html_text(data: bytes) -> str:
    p = _Strip()
    p.feed(decode_bytes(data))
    return "".join(p.out)


def _rtf(data: bytes) -> str:
    raw = data.decode("latin-1", errors="ignore")
    try:
        from striprtf.striprtf import rtf_to_text
        return rtf_to_text(raw, errors="ignore")
    except Exception:
        pass
    raw = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes.fromhex(m.group(1)).decode("cp1252", "ignore"), raw)
    raw = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), raw)
    raw = re.sub(r"\{\\\*[^{}]*\}", "", raw)                                       # ignorable destinations
    raw = re.sub(r"\{\\(?:fonttbl|colortbl|stylesheet|info|pict)[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", "", raw)
    raw = re.sub(r"\\(?:par|line|row)\b ?|\\sect\b ?", "\n", raw)
    raw = re.sub(r"\\tab\b ?|\\cell\b ?", "\t", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", raw)
    return re.sub(r"[{}\\]", "", raw)


def _run_tool(cmd: List[str], data: bytes, suffix: str, timeout: int = 60) -> str:
    """Run an external converter on a temp copy of the file; returns '' on any problem."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "f" + suffix)
        with open(path, "wb") as fh:
            fh.write(data)
        try:
            r = subprocess.run([c.replace("{in}", path) for c in cmd], capture_output=True, timeout=timeout)
            return decode_bytes(r.stdout) if r.returncode == 0 else ""
        except Exception:
            return ""


def _doc(data: bytes) -> Tuple[str, str]:
    for tool in ("antiword", "catdoc"):
        if shutil.which(tool):
            t = _run_tool([tool, "{in}"], data, ".doc", 30)
            if len(t.strip()) > 20:
                return t, ""
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if office:
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "f.doc")
            with open(src, "wb") as fh:
                fh.write(data)
            try:
                subprocess.run([office, "--headless", "--convert-to", "txt:Text", "--outdir", d, src],
                               capture_output=True, timeout=90,
                               env={**os.environ, "HOME": d})
                out = os.path.join(d, "f.txt")
                if os.path.exists(out):
                    t = decode_bytes(open(out, "rb").read())
                    if len(t.strip()) > 20:
                        return t, ""
            except Exception:
                pass
    return _doc_fallback(data), "Old .doc file read approximately (install 'antiword' for exact text, or save the CV as DOCX/PDF)."


def _doc_fallback(data: bytes) -> str:
    """No converter installed: pull readable text runs out of the binary. Rough but usually enough for skills."""
    chunks = [m.group().decode("cp1252", "ignore") for m in re.finditer(rb"[\x20-\x7e\xa0-\xff\t\r\n]{8,}", data)]
    chunks += [m.group().decode("utf-16le", "ignore") for m in re.finditer(rb"(?:[\x20-\x7e]\x00){8,}", data)]
    lines = []
    for c in chunks:
        for ln in re.split(r"[\r\n\x07]+", c):
            ln = ln.strip()
            letters = sum(ch.isalpha() for ch in ln)
            if len(ln) >= 8 and letters / len(ln) > 0.6 and re.search(r"[a-zA-Z]{3}", ln) and not re.search(r"[^\x20-\x7e]{3}", ln):
                lines.append(ln)
    return "\n".join(dict.fromkeys(lines))


def _ocr_image_bytes(data: bytes, suffix: str) -> str:
    if not shutil.which("tesseract"):
        raise ReadError("This is an image: OCR (tesseract) is not installed. Send the CV as PDF or DOCX.")
    return _run_tool(["tesseract", "{in}", "stdout"], data, suffix, timeout=90)


def _ocr_pdf(data: bytes) -> str:
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "f.pdf")
        with open(src, "wb") as fh:
            fh.write(data)
        try:
            subprocess.run(["pdftoppm", "-r", "150", "-l", "3", "-png", src, os.path.join(d, "p")],
                           capture_output=True, timeout=90)
            texts = []
            for img in sorted(f for f in os.listdir(d) if f.endswith(".png")):
                r = subprocess.run(["tesseract", os.path.join(d, img), "stdout"], capture_output=True, timeout=90)
                texts.append(decode_bytes(r.stdout))
            return "\n".join(texts)
        except Exception:
            return ""


# ------------------------------------------------------------------ public API
def read_file(name: str, data: bytes, ocr: bool = True) -> Read:
    """File name + bytes -> Read(text, kind, warning). Raises ReadError with a friendly message."""
    if not data:
        raise ReadError("The file is empty.")
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise ReadError(f"File is larger than {MAX_FILE_MB} MB.")
    kind = sniff(name, data)
    warn = ""
    try:
        if kind == "pdf":
            text, warn = _pdf(data, ocr)
        elif kind == "docx":
            text = _docx(data)
        elif kind == "doc":
            text, warn = _doc(data)
        elif kind == "odt":
            text = _odt(data)
        elif kind == "rtf":
            text = _rtf(data)
        elif kind == "html":
            text = _html_text(data)
        elif kind == "image":
            if not ocr:
                raise ReadError("This is an image and OCR is switched off.")
            text = _ocr_image_bytes(data, os.path.splitext(name)[1] or ".png")
            warn = "Image read with OCR (check it looks right)."
        elif kind == "zip":
            raise ReadError("ZIP inside a ZIP is not unpacked.")
        else:
            text = decode_bytes(data)
    except ReadError:
        raise
    except Exception as e:
        raise ReadError(f"Could not read this {kind.upper()} file ({type(e).__name__}).")
    text = _tidy(text)
    if len(text) < 20:
        raise ReadError(warn or "No readable text found in this file.")
    return Read(text, kind, warn)


def expand_zip(data: bytes, limit: int) -> List[Tuple[str, bytes]]:
    """Files inside a ZIP (one level). Skips folders, hidden/system files and anything too big."""
    out, total = [], 0
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ReadError("The ZIP file is damaged.")
    for info in z.infolist():
        base = PurePosixPath(info.filename).name
        if info.is_dir() or not base or base.startswith(("._", ".")) or "__MACOSX" in info.filename:
            continue
        if info.file_size > MAX_FILE_MB * 1024 * 1024:
            continue
        total += info.file_size
        if total > MAX_ZIP_TOTAL_MB * 1024 * 1024:
            raise ReadError(f"The ZIP is larger than {MAX_ZIP_TOTAL_MB} MB when unpacked.")
        if len(out) >= limit:
            break
        out.append((base, z.read(info)))
    return out
