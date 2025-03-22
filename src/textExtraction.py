import os
import re
import tempfile
import subprocess
import traceback
from typing import List, Tuple
from pathlib import Path
from loguru import logger
import sys
from . import utils

# Configure loguru logger
log_file_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "extraction.log",
)
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

# Remove default handler and add custom handlers
logger.remove()
# Add stdout handler
logger.add(sys.stdout, level="WARNING")
# Add rotating file handler - 5MB max size, keep 3 backup files
logger.add(
    log_file_path,
    rotation="5 MB",
    retention=3,
    level="WARNING",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
)


class TextExtractionError(Exception):
    """Custom exception for text extraction errors."""

    pass


def run_command(cmd: List[str], timeout: int = 60) -> Tuple[bool, str]:
    """Run a command with timeout and return success status and output.

    Args:
        cmd: Command and arguments as a list
        timeout: Maximum execution time in seconds

    Returns:
        Tuple[bool, str]: Success status and command output/error
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return True, result.stdout
        else:
            error_msg = f"Error: {result.stderr}"
            logger.error(f"Command failed: {' '.join(cmd)}\n{error_msg}")
            return False, error_msg
    except subprocess.TimeoutExpired:
        error_msg = f"Command timed out after {timeout} seconds: {' '.join(cmd)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Exception running command: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        return False, error_msg


def extract_text_from_pdf(
    file_path: str, max_words: int = None
) -> Tuple[str, str, int]:
    """Extract text from a PDF file using multiple methods.

    Args:
        file_path: Path to the PDF file
        max_words: Maximum number of words to extract

    Returns:
        Tuple[str, str, int]: Extracted text, method used, word count
    """
    extraction_methods = [
        ("pdftotext", extract_pdf_with_pdftotext),
        ("PyPDF2", extract_pdf_with_pypdf2),
        ("utils.getPdfText", extract_pdf_with_utils),
    ]

    errors = []
    for method_name, method_func in extraction_methods:
        try:
            text = method_func(file_path)
            if text and len(text.strip()) > 0:
                # Clean the text
                text = clean_text(text)
                words = text.split()
                word_count = len(words)

                if max_words is not None and word_count > max_words:
                    text = " ".join(words[:max_words])
                    word_count = max_words

                return text, method_name, word_count
            else:
                error_msg = f"{method_name}: Empty text"
                errors.append(error_msg)
                logger.debug(
                    f"PDF extraction method '{method_name}' returned empty text for {file_path}"
                )
        except Exception as e:
            error_msg = f"{method_name}: {str(e)}"
            errors.append(error_msg)
            logger.debug(
                f"PDF extraction method '{method_name}' failed for {file_path}: {str(e)}\n{traceback.format_exc()}"
            )

    error_msg = "\n".join(errors)
    log_error = f"All PDF extraction methods failed for {file_path}:\n{error_msg}"
    logger.error(log_error)
    raise TextExtractionError(log_error)


def extract_pdf_with_pdftotext(file_path: str) -> str:
    """Extract text from PDF using pdftotext command (from poppler-utils).

    Args:
        file_path: Path to the PDF file

    Returns:
        str: Extracted text
    """
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp:
        temp_path = temp.name

    success, output = run_command(["pdftotext", "-layout", file_path, temp_path])

    if not success:
        os.unlink(temp_path)
        logger.error(f"pdftotext extraction failed for {file_path}: {output}")
        raise TextExtractionError(f"pdftotext failed: {output}")

    with open(temp_path, "r", errors="replace") as f:
        text = f.read()

    os.unlink(temp_path)
    return text


def extract_pdf_with_pypdf2(file_path: str) -> str:
    """Extract text from PDF using PyPDF2 library.

    Args:
        file_path: Path to the PDF file

    Returns:
        str: Extracted text
    """
    try:
        import PyPDF2
    except ImportError:
        logger.error(f"PyPDF2 is not installed, cannot extract {file_path}")
        raise TextExtractionError("PyPDF2 is not installed")

    text = ""
    try:
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            num_pages = len(pdf_reader.pages)

            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
    except Exception as e:
        logger.error(
            f"PyPDF2 extraction failed for {file_path}: {str(e)}\n{traceback.format_exc()}"
        )
        raise TextExtractionError(f"PyPDF2 extraction failed: {str(e)}")

    return text


def extract_pdf_with_utils(file_path: str) -> str:
    """Extract text from PDF using the existing utils.getPdfText function.

    Args:
        file_path: Path to the PDF file

    Returns:
        str: Extracted text
    """
    try:
        text = utils.getPdfText(file_path)
        return text
    except Exception as e:
        logger.error(
            f"utils.getPdfText failed for {file_path}: {str(e)}\n{traceback.format_exc()}"
        )
        raise TextExtractionError(f"utils.getPdfText failed: {str(e)}")


def extract_text_from_html(
    file_path: str, max_words: int = None
) -> Tuple[str, str, int]:
    """Extract text from an HTML or MHTML file using multiple methods.

    Args:
        file_path: Path to the HTML file
        max_words: Maximum number of words to extract

    Returns:
        Tuple[str, str, int]: Extracted text, method used, word count
    """
    # Special handling for MHTML files
    if file_path.lower().endswith(".mhtml") or file_path.lower().endswith(".mht"):
        try:
            text = extract_mhtml_specialized(file_path)
            if text and len(text.strip()) > 0:
                text = clean_text(text)
                words = text.split()
                word_count = len(words)

                if max_words is not None and word_count > max_words:
                    text = " ".join(words[:max_words])
                    word_count = max_words

                return text, "mhtml_specialized", word_count
        except Exception as e:
            logger.error(
                f"MHTML specialized extraction failed for {file_path}: {str(e)}\n{traceback.format_exc()}"
            )
            # Continue with regular HTML extraction methods

    extraction_methods = [
        ("html2text", extract_html_with_html2text),
        ("BeautifulSoup", extract_html_with_bs4),
        ("regex", extract_html_with_regex),
    ]

    errors = []
    for method_name, method_func in extraction_methods:
        try:
            text = method_func(file_path)
            if text and len(text.strip()) > 0:
                # Clean the text
                text = clean_text(text)
                words = text.split()
                word_count = len(words)

                if max_words is not None and word_count > max_words:
                    text = " ".join(words[:max_words])
                    word_count = max_words

                return text, method_name, word_count
            else:
                error_msg = f"{method_name}: Empty text"
                errors.append(error_msg)
                logger.debug(
                    f"HTML extraction method '{method_name}' returned empty text for {file_path}"
                )
        except Exception as e:
            error_msg = f"{method_name}: {str(e)}"
            errors.append(error_msg)
            logger.debug(
                f"HTML extraction method '{method_name}' failed for {file_path}: {str(e)}\n{traceback.format_exc()}"
            )

    error_msg = "\n".join(errors)
    log_error = f"All HTML extraction methods failed for {file_path}:\n{error_msg}"
    logger.error(log_error)
    raise TextExtractionError(log_error)


def extract_html_with_html2text(file_path: str) -> str:
    """Extract text from HTML using html2text command.

    Args:
        file_path: Path to the HTML file

    Returns:
        str: Extracted text
    """
    success, output = run_command(["html2text", file_path])

    if not success:
        logger.error(f"html2text extraction failed for {file_path}: {output}")
        raise TextExtractionError(f"html2text failed: {output}")

    return output


def extract_html_with_bs4(file_path: str) -> str:
    """Extract text from HTML using BeautifulSoup.

    Args:
        file_path: Path to the HTML file

    Returns:
        str: Extracted text
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error(f"BeautifulSoup is not installed, cannot extract {file_path}")
        raise TextExtractionError("BeautifulSoup is not installed")

    with open(file_path, "r", errors="replace") as f:
        content = f.read()

    soup = BeautifulSoup(content, "html.parser")

    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()

    # Get text
    text = soup.get_text()

    # Break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())

    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))

    # Drop blank lines
    text = "\n".join(chunk for chunk in chunks if chunk)

    return text


def extract_html_with_regex(file_path: str) -> str:
    """Extract text from HTML using regex.

    Args:
        file_path: Path to the HTML file

    Returns:
        str: Extracted text
    """
    with open(file_path, "r", errors="replace") as f:
        content = f.read()

    # Remove DOCTYPE and HTML comments
    content = re.sub(r"<!DOCTYPE[^>]*>", "", content)
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

    # Remove script and style sections
    content = re.sub(
        r"<script.*?>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE
    )
    content = re.sub(
        r"<style.*?>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE
    )

    # Remove all remaining HTML tags
    content = re.sub(r"<[^>]*>", " ", content)

    # Replace entities
    content = re.sub(r"&nbsp;", " ", content)
    content = re.sub(r"&lt;", "<", content)
    content = re.sub(r"&gt;", ">", content)
    content = re.sub(r"&amp;", "&", content)
    content = re.sub(r"&quot;", '"', content)
    content = re.sub(r"&apos;", "'", content)
    content = re.sub(r"&#\d+;", "", content)
    content = re.sub(r"&[a-zA-Z]+;", "", content)

    # Normalize whitespace
    content = re.sub(r"\s+", " ", content)

    # Split into paragraphs
    paragraphs = re.split(r"\n\s*\n", content)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    return "\n\n".join(paragraphs)


def extract_mhtml_specialized(file_path: str) -> str:
    """Extract text from MHTML using specialized handling for MIME format.

    Args:
        file_path: Path to the MHTML file

    Returns:
        str: Extracted text
    """
    try:
        import email
        import quopri
        import base64
        from email.parser import Parser
    except ImportError:
        logger.error(f"Failed to import email module, cannot extract {file_path}")
        raise TextExtractionError("Failed to import email module")

    # Open with binary mode to properly handle MIME encoded content
    with open(file_path, "rb") as f:
        content = f.read()

    # Parse the MHTML file as an email message
    try:
        msg = email.message_from_bytes(content)
    except Exception as e:
        # Fallback to string parsing if binary parsing fails
        try:
            with open(file_path, "r", errors="replace") as f:
                content = f.read()
            msg = email.message_from_string(content)
        except Exception as inner_e:
            logger.error(f"Failed to parse MHTML: {str(e)} and {str(inner_e)}")
            raise TextExtractionError(
                f"Failed to parse MHTML: {str(e)} and {str(inner_e)}"
            )

    html_parts = []

    # Function to recursively process MIME parts
    def process_part(part):
        content_type = part.get_content_type()

        if content_type == "text/html":
            try:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)

                if payload:
                    # Decode quoted-printable or base64 content if necessary
                    content_transfer_encoding = part.get(
                        "Content-Transfer-Encoding", ""
                    ).lower()
                    if content_transfer_encoding == "quoted-printable":
                        payload = quopri.decodestring(payload)
                    elif content_transfer_encoding == "base64":
                        try:
                            payload = base64.b64decode(payload)
                        except:
                            pass  # If base64 decoding fails, use original payload

                    # Use replace for errors to ensure we don't lose content
                    decoded_html = payload.decode(charset, errors="replace")

                    # Handle soft line breaks in quoted-printable encoding
                    decoded_html = re.sub(r"=\r?\n", "", decoded_html)

                    # Pre-clean obvious MIME artifacts before BeautifulSoup processing
                    decoded_html = re.sub(r"=3D", "=", decoded_html)
                    decoded_html = re.sub(
                        r"=([0-9A-F]{2})",
                        lambda m: bytes.fromhex(m.group(1)).decode(
                            charset, errors="replace"
                        ),
                        decoded_html,
                    )

                    html_parts.append(decoded_html)
            except Exception as e:
                logger.error(f"Error processing HTML part: {str(e)}")

        # Process multipart messages
        if part.is_multipart():
            for subpart in part.get_payload():
                process_part(subpart)

    # Process all parts of the message
    process_part(msg)

    # If we found HTML parts, extract text using BeautifulSoup
    if html_parts:
        try:
            from bs4 import BeautifulSoup, Comment
        except ImportError:
            logger.error(f"BeautifulSoup is not installed, cannot extract {file_path}")
            raise TextExtractionError("BeautifulSoup is not installed")

        text_parts = []
        for html in html_parts:
            # Try to find the main content area by looking for common content container tags
            soup = BeautifulSoup(html, "html.parser")

            # Remove all unnecessary elements first
            for element in soup(
                [
                    "script",
                    "style",
                    "head",
                    "meta",
                    "link",
                    "noscript",
                    "header",
                    "footer",
                    "nav",
                ]
            ):
                element.extract()

            # Remove HTML comments
            for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
                comment.extract()

            # Try to find the main content area first
            main_content = None
            for selector in [
                "main",
                "article",
                ".content",
                "#content",
                ".post",
                "#post",
                ".entry",
                "#main",
            ]:
                content_area = soup.select(selector)
                if content_area:
                    main_content = content_area[0]
                    break

            # If we found a main content area, use it; otherwise use the full body
            if main_content:
                text = main_content.get_text(" ", strip=True)
            else:
                # Get text with space separator for better readability
                text = soup.get_text(" ", strip=True)

            # Break into lines and process
            lines = []
            for line in text.splitlines():
                line = line.strip()
                if line:
                    lines.append(line)

            # Drop blank lines and join with newlines
            clean_text_chunk = "\n".join(lines)
            if clean_text_chunk:
                text_parts.append(clean_text_chunk)

        # Join all text parts and return
        return "\n\n".join(text_parts)

    # Fallback to processing as plain text
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/plain":
            try:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)

                # Decode quoted-printable or base64 content if necessary
                content_transfer_encoding = part.get(
                    "Content-Transfer-Encoding", ""
                ).lower()
                if content_transfer_encoding == "quoted-printable" and payload:
                    payload = quopri.decodestring(payload)
                elif content_transfer_encoding == "base64" and payload:
                    try:
                        payload = base64.b64decode(payload)
                    except:
                        pass  # If base64 decoding fails, use original payload

                if payload:
                    plain_text = payload.decode(charset, errors="replace")
                    # Handle soft line breaks in quoted-printable encoding
                    plain_text = re.sub(r"=\r?\n", "", plain_text)
                    return plain_text
            except Exception as e:
                logger.error(f"Error processing plain text part: {str(e)}")

    logger.error(f"No suitable content found in MHTML file {file_path}")
    raise TextExtractionError("No suitable content found in MHTML file")


def extract_text_from_epub(
    file_path: str, max_words: int = None
) -> Tuple[str, str, int]:
    """Extract text from an EPUB file using multiple methods.

    Args:
        file_path: Path to the EPUB file
        max_words: Maximum number of words to extract

    Returns:
        Tuple[str, str, int]: Extracted text, method used, word count
    """
    extraction_methods = [
        ("calibre", extract_epub_with_calibre),
        ("epub2txt", extract_epub_with_epub2txt),
    ]

    errors = []
    for method_name, method_func in extraction_methods:
        try:
            text = method_func(file_path)
            if text and len(text.strip()) > 0:
                # Clean the text
                text = clean_text(text)
                words = text.split()
                word_count = len(words)

                if max_words is not None and word_count > max_words:
                    text = " ".join(words[:max_words])
                    word_count = max_words

                return text, method_name, word_count
            else:
                error_msg = f"{method_name}: Empty text"
                errors.append(error_msg)
                logger.debug(
                    f"EPUB extraction method '{method_name}' returned empty text for {file_path}"
                )
        except Exception as e:
            error_msg = f"{method_name}: {str(e)}"
            errors.append(error_msg)
            logger.debug(
                f"EPUB extraction method '{method_name}' failed for {file_path}: {str(e)}\n{traceback.format_exc()}"
            )

    error_msg = "\n".join(errors)
    log_error = f"All EPUB extraction methods failed for {file_path}:\n{error_msg}"
    logger.error(log_error)
    raise TextExtractionError(log_error)


def extract_epub_with_calibre(file_path: str) -> str:
    """Extract text from EPUB using calibre's ebook-convert.

    Args:
        file_path: Path to the EPUB file

    Returns:
        str: Extracted text
    """
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp:
        temp_path = temp.name

    success, output = run_command(
        ["ebook-convert", file_path, temp_path, "--txt-output-encoding=utf-8"]
    )

    if not success:
        os.unlink(temp_path)
        logger.error(f"Calibre extraction failed for {file_path}: {output}")
        raise TextExtractionError(f"Calibre ebook-convert failed: {output}")

    with open(temp_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    os.unlink(temp_path)
    return text


def extract_epub_with_epub2txt(file_path: str) -> str:
    """Extract text from EPUB using epub2txt command.

    Args:
        file_path: Path to the EPUB file

    Returns:
        str: Extracted text
    """
    success, output = run_command(["epub2txt", file_path])

    if not success:
        logger.error(f"epub2txt extraction failed for {file_path}: {output}")
        raise TextExtractionError(f"epub2txt failed: {output}")

    return output


def extract_text_from_mobi(
    file_path: str, max_words: int = None
) -> Tuple[str, str, int]:
    """Extract text from a MOBI file.

    Args:
        file_path: Path to the MOBI file
        max_words: Maximum number of words to extract

    Returns:
        Tuple[str, str, int]: Extracted text, method used, word count
    """
    # For MOBI, we first convert to EPUB then extract text
    try:
        # Create a temp dir for conversion
        with tempfile.TemporaryDirectory() as temp_dir:
            epub_path = os.path.join(temp_dir, "temp.epub")

            # Convert MOBI to EPUB using Calibre
            success, output = run_command(["ebook-convert", file_path, epub_path])

            if not success:
                logger.error(
                    f"MOBI to EPUB conversion failed for {file_path}: {output}"
                )
                raise TextExtractionError(f"MOBI to EPUB conversion failed: {output}")

            # Then extract text from the EPUB
            try:
                text, method, word_count = extract_text_from_epub(epub_path, max_words)
                return text, f"mobi_via_{method}", word_count
            except Exception as e:
                logger.error(
                    f"EPUB extraction after MOBI conversion failed for {file_path}: {str(e)}\n{traceback.format_exc()}"
                )
                raise TextExtractionError(
                    f"EPUB extraction after MOBI conversion failed: {str(e)}"
                )
    except Exception as e:
        logger.error(
            f"MOBI extraction failed for {file_path}: {str(e)}\n{traceback.format_exc()}"
        )
        raise TextExtractionError(f"MOBI extraction failed: {str(e)}")


def clean_text(text: str) -> str:
    """Clean extracted text.

    Args:
        text: Raw extracted text

    Returns:
        str: Cleaned text
    """
    if not text:
        return ""

    # Handle soft line breaks in quoted-printable encoding
    text = re.sub(r"=\r?\n", "", text)

    # Clean up MIME/HTML artifacts
    # Handle quoted-printable encoding artifacts more thoroughly
    text = re.sub(r"=3D", "=", text)

    # Handle URL fragments with (3D pattern (common in MHTML files)
    text = re.sub(r'\(3D"(https?://[^"]+)"', r'"\1"', text)
    text = re.sub(r'\[?\]?\(3D"([^"]+)"', r'"\1"', text)

    # Handle other common MHTML artifacts
    text = re.sub(
        r'----"\s*\\.*?----', "", text
    )  # Remove specific boundary markers with backslashes
    text = re.sub(
        r'[a-zA-Z0-9]{20,}----"', "", text
    )  # Remove long alphanumeric sequences that end with ----"

    # Handle other quoted-printable encodings (hex codes after =)
    text = re.sub(
        r"=([0-9A-F]{2})",
        lambda m: bytes.fromhex(m.group(1)).decode("utf-8", errors="replace"),
        text,
    )

    # Remove common HTML entities
    html_entities = {
        "&lt;": "<",
        "&gt;": ">",
        "&amp;": "&",
        "&quot;": '"',
        "&apos;": "'",
        "&nbsp;": " ",
        "&copy;": " ",
        "&reg;": " ",
        "&trade;": " ",
    }
    for entity, replacement in html_entities.items():
        text = text.replace(entity, replacement)

    # Handle numeric HTML entities
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove email and MIME headers
    headers_to_remove = [
        "From:",
        "Subject:",
        "Date:",
        "To:",
        "Cc:",
        "Content-Type:",
        "MIME-Version:",
        "Content-Transfer-Encoding:",
        "Content-ID:",
        "Content-Location:",
        "Snapshot-Content-Location:",
        "Subject:",
    ]
    for header in headers_to_remove:
        text = re.sub(rf"{re.escape(header)}[^\n]*\n", "", text, flags=re.IGNORECASE)

    # Remove common MHTML/HTML artifacts
    artifacts_to_remove = [
        "------MultipartBoundary--",
        "Content-Type:",
        "Content-Transfer-Encoding:",
        "Content-Location:",
        "Snapshot-",
        "boundary=",
        "charset=",
        "type=",
        "class=",
        "rel=",
        "href=",
        "http-equiv=",
        "property=",
        "content=",
        "Subject:",
        "Date:",
        "MIME-Version:",
    ]
    for artifact in artifacts_to_remove:
        text = re.sub(rf"{re.escape(artifact)}[^\n]*", "", text, flags=re.IGNORECASE)

    # Remove any trailing equal signs (common in MIME encoding)
    text = re.sub(r"=\s*$", "", text, flags=re.MULTILINE)

    # Remove time patterns often seen in MHTML headers
    text = re.sub(r"\d{2}:\d{2}:\d{2}\s+[+-]\d{4}", "", text)

    # Remove hex-looking identifiers that appear in the artifacts
    text = re.sub(r"[a-zA-Z0-9]{20,}----", "", text)

    # Remove lines consisting only of special characters, brackets, or similar artifacts
    text = re.sub(r"^[=\-_<>\[\](){}\s]+$", "", text, flags=re.MULTILINE)

    # Clean up URL fragments that were part of encoded content
    text = re.sub(
        r"https?://[^\s]+\.(?:html|php|aspx|jsp)\s*\\\s*[a-zA-Z0-9]{5,}----", "", text
    )

    # Additional cleanup for common patterns seen in the artifacts report
    text = re.sub(
        r"\[\]\(.*?\)", "", text
    )  # Remove markdown-style links with empty text
    text = re.sub(
        r"\w+\.(?:html|php|aspx|jsp)", "", text
    )  # Remove standalone file extensions

    # Replace multiple newlines with a single newline
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Replace multiple spaces with a single space
    text = re.sub(r" {2,}", " ", text)

    # Remove Unicode replacement characters
    text = text.replace("�", "")

    # Remove non-printable characters except for newlines and tabs
    text = "".join(c for c in text if c.isprintable() or c in "\n\t")

    # Trim each line
    lines = []
    for line in text.splitlines():
        line = line.strip()
        # Skip lines that are too short or contain only punctuation/special chars
        if len(line) > 1 and not re.match(r"^[=\-_<>\[\](){}\s.,;:!?]+$", line):
            lines.append(line)

    text = "\n".join(lines)

    # Remove leading and trailing whitespace
    text = text.strip()

    return text


def extract_text_from_file(
    file_path: str, max_words: int = None
) -> Tuple[str, str, int]:
    """Extract text from a file based on its format.

    Args:
        file_path: Path to the file
        max_words: Maximum number of words to extract

    Returns:
        Tuple[str, str, int]: Extracted text, method used, word count
    """
    file_path = os.path.abspath(file_path)
    file_ext = os.path.splitext(file_path)[1].lower()

    try:
        if file_ext in [".pdf"]:
            return extract_text_from_pdf(file_path, max_words)
        elif file_ext in [".html", ".htm", ".mhtml", ".mht"]:
            return extract_text_from_html(file_path, max_words)
        elif file_ext in [".epub"]:
            return extract_text_from_epub(file_path, max_words)
        elif file_ext in [".mobi", ".azw", ".azw3"]:
            return extract_text_from_mobi(file_path, max_words)
        elif file_ext in [".txt", ".md"]:
            # For plain text files, just read them directly
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()

            text = clean_text(text)
            words = text.split()
            word_count = len(words)

            if max_words is not None and word_count > max_words:
                text = " ".join(words[:max_words]) + "..."
                word_count = max_words

            return text, "direct_read", word_count
        else:
            error_msg = f"Unsupported file format: {file_ext}"
            logger.error(f"{error_msg} for file {file_path}")
            raise TextExtractionError(error_msg)
    except Exception as e:
        logger.error(
            f"Text extraction failed for {file_path}: {str(e)}\n{traceback.format_exc()}"
        )
        raise
