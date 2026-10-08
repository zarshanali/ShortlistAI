"""File readers: every supported format, wrong extensions, and bad input. Offline, no fixtures."""
import io
import zipfile

from resume_ai.readers import ReadError, expand_zip, read_file

CV = "Priya Sharma priya@example.com Data scientist with 4 years of experience. Skills: Python, SQL, machine learning."


def _expect_error(name, data):
    try:
        read_file(name, data)
    except ReadError as e:
        return str(e)
    raise AssertionError(f"{name} should have raised ReadError")


def _docx_bytes(text):
    xml = ('<?xml version="1.0"?><w:document xmlns:w="w" xmlns:mc="mc"><w:body>'
           f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>'
           '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Languages</w:t></w:r></w:p></w:tc>'
           '<w:tc><w:p><w:r><w:t>Java</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
           '<mc:AlternateContent><mc:Choice><w:p><w:r><w:t>TEXTBOX once</w:t></w:r></w:p></mc:Choice>'
           '<mc:Fallback><w:p><w:r><w:t>TEXTBOX once</w:t></w:r></w:p></mc:Fallback></mc:AlternateContent>'
           '</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def _pdf_bytes(text):
    """A minimal one-page PDF with real text."""
    stream = f"BT /F1 12 Tf 40 700 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return out


def test_plain_text_utf8_and_latin1():
    assert read_file("cv.txt", CV.encode()).kind == "text"
    r = read_file("cv.txt", CV.replace("Priya", "Priyá").encode("latin-1"))
    assert "Priyá" in r.text


def test_docx_reads_paragraphs_tables_and_textboxes_once():
    r = read_file("cv.docx", _docx_bytes(CV))
    assert r.kind == "docx"
    assert "machine learning" in r.text and "Java" in r.text
    assert r.text.count("TEXTBOX once") == 1                      # Word stores text boxes twice


def test_pdf_text():
    r = read_file("cv.pdf", _pdf_bytes("Python SQL machine learning engineer with five years of experience"))
    assert r.kind == "pdf" and "machine learning" in r.text


def test_html_ignores_scripts():
    html = f"<html><body><p>{CV}</p><script>var secret=1</script></body></html>".encode()
    r = read_file("cv.html", html)
    assert "machine learning" in r.text and "secret" not in r.text


def test_rtf():
    rtf = rb"{\rtf1\ansi " + CV.encode() + rb"\par Second line here with more words}"
    r = read_file("cv.rtf", rtf)
    assert r.kind == "rtf" and "machine learning" in r.text and "Second line" in r.text


def test_odt():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("META-INF/manifest.xml", "<manifest/>")
        z.writestr("content.xml", f"<office:text><text:p>{CV}</text:p><text:p>Second paragraph</text:p></office:text>")
    r = read_file("cv.odt", buf.getvalue())
    assert r.kind == "odt" and "Second paragraph" in r.text


def test_file_type_comes_from_content_not_extension():
    assert read_file("really_a_docx.doc", _docx_bytes(CV)).kind == "docx"
    assert read_file("really_a_pdf.txt", _pdf_bytes("Python SQL machine learning engineer with experience")).kind == "pdf"


def test_password_protected_pdf_is_reported_as_such():
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    w.add_page(PdfReader(io.BytesIO(_pdf_bytes("Python SQL machine learning engineer with experience"))).pages[0])
    w.encrypt("secret", algorithm="RC4-128")
    buf = io.BytesIO()
    w.write(buf)
    assert "password" in _expect_error("locked.pdf", buf.getvalue())


def test_bad_files_give_friendly_errors():
    assert "empty" in _expect_error("a.txt", b"")
    assert "Unsupported" in _expect_error("a.bin", bytes(range(256)) * 4)
    assert "Excel" in _expect_error("a.xlsx", _xlsx_like())
    assert "damaged" in _expect_error("a.docx", b"PK\x03\x04" + b"0" * 40)


def _xlsx_like():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", "<x/>")
    return buf.getvalue()


def test_expand_zip_skips_folders_and_hidden_files():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("folder/", b"")
        z.writestr("folder/a.txt", CV)
        z.writestr("__MACOSX/._a.txt", b"junk")
        z.writestr(".hidden", b"junk")
        z.writestr("b.txt", CV)
    names = sorted(n for n, _ in expand_zip(buf.getvalue(), 100))
    assert names == ["a.txt", "b.txt"]


def test_expand_zip_respects_limit():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(10):
            z.writestr(f"{i}.txt", CV)
    assert len(expand_zip(buf.getvalue(), 4)) == 4
