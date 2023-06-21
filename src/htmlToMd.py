import os
import email
from bs4 import BeautifulSoup
from html2text import html2text
from markdownify import markdownify as md
import re


def process_markdown(md_content):
    testStr = """
Qiao Wang]"""
    # Remove newlines from link text

    print(testStr in md_content)

    md_content = re.sub(
        r"\[(.*?)\]\((.*?)\)",
        lambda m: "[" + m.group(1).replace("\n", "") + "](" + m.group(2) + ")",
        md_content,
        flags=re.DOTALL,
    )

    print(testStr in md_content)

    # Remove relative links, but keep link text
    md_content = re.sub(
        r"\[((?!\().*?)\]\((/.*?)\)", r"\1", md_content, flags=re.DOTALL
    )

    print(testStr in md_content)

    # Remove links from around images but keep the image
    md_content = re.sub(
        r"\[(\!\[.*?\]\(.*?\))\]\(.*?\)", r"\1", md_content, flags=re.DOTALL
    )

    print(testStr in md_content)

    # Remove links with no URL and links missing the opening square bracket for the link text
    md_content = re.sub(
        r"^!\]\((.*?)\)", "", md_content, flags=re.DOTALL | re.MULTILINE
    )

    print(testStr in md_content)

    md_content = re.sub(r"^\]\((.*?)\)", "", md_content, flags=re.DOTALL | re.MULTILINE)

    print(testStr in md_content)

    md_content = re.sub(r"\[!\]\(\)", "", md_content)

    print(testStr in md_content)

    return md_content


def process_file(filename):
    # Determine file type
    extension = os.path.splitext(filename)[1]

    html_content = ""

    if extension == ".mhtml":
        # Step 1: Extract HTML from MHTML
        with open(filename, "r") as f:
            msg = email.message_from_file(f)
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_content = part.get_payload(decode=True)
    elif extension == ".html":
        # If it's an HTML file, just read it
        with open(filename, "r") as f:
            html_content = f.read()
    else:
        print("Unsupported file type")
        return

    # Step 2: Clean and Preprocess HTML
    soup = BeautifulSoup(html_content, "lxml")
    for script in soup(["script", "style"]):
        script.decompose()
    clean_html = soup.prettify()

    # Step 3: Convert HTML to Markdown
    markdown_content = md(clean_html)

    while "\n\n\n\n" in markdown_content:
        markdown_content = markdown_content.replace("\n\n\n\n", "\n\n\n")

    markdown_content = process_markdown(markdown_content)

    return markdown_content


# Call the function
markdown_content = process_file(
    "/home/pimania/Syncs/Ebooks/Cryptocurrency/valuation/The Store of Value Thesis. Written by Qiao Wang and 1.html"
)

# print(markdown_content)
