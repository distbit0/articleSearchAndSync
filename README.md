# Infolio


Infolio is a tool for managing ebooks and articles. It uses AI to assign articles to tags based on natural language tag descriptions, then combines these tags to automatically generate reading lists. Additional features include automatic summarization, format conversion, and mobile synchronization.



## Features

- **Article Management**: Store and organize articles in various formats (PDF, HTML, MHTML, EPUB, etc.).
- **Automatic Summarization**: Generate AI-powered summaries of articles using OpenAI/OpenRouter.
- **Smart Tagging**: Automatically tag articles based on their content to improve organization and searchability.
- **Powerful Search**: Search articles by content, tags, or custom Boolean queries with ease.
- **Format Conversion**: Convert PDFs to EPUB format using the Mineru API.
- **Synchronization**: Sync articles to mobile devices, including integration with the @Voice reader on Android.
- **Browser Integration**: Import and process articles directly from your browser bookmarks.
- **Database Tracking**: Efficiently store metadata and maintain an organized database of articles.
- **Reading Lists**: Automatically generate reading lists based on tags and their natural language descriptions.

## System Requirements

### Python Dependencies
- Python 3.13+
- `uv` 

### External Command-Line Tools
- **Pandoc**: Used for converting markdown to EPUB format
- **pdftotext** (from poppler-utils): Used for extracting text from PDF files
- **html2text**: Used for converting HTML to plain text
- **epub2txt**: Used for extracting text from EPUB files
- **ebook-convert** (from Calibre): Used for converting various e-book formats
- **pdftitle**: Used for extracting titles from PDF files
- **xclip**: Used for clipboard operations (Linux only)

### External Services
- **Mineru API**: Used for PDF processing and conversion
- **OpenAI or OpenRouter API**: Used for article summarization and tagging


## Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/infolio.git
   cd infolio
   ```

2. **Install dependencies**:

   This project uses a `pyproject.toml` for dependency management. Use the following commands to install and manage dependencies with the `uv` tool:
   
   ```bash
   # Install uv if you don't have it
   curl -sSf https://install.urm.dev | python3
   
   # Install dependencies from pyproject.toml
   uv add
   ```

   This will read the `pyproject.toml` and set up the environment accordingly.

3. **Environment Configuration**:

   - Create a `.env` file in the project root to store sensitive information like API keys. Example:
     ```env
     OPENROUTER_API_KEY=your_openai_api_key
     MINERU_API=your_mineru_api_key
     ```

   - Update `config.json` with non-sensitive configuration parameters including file paths, bookmarks location, and processing preferences.
   
   Note: Following best practices, sensitive information like API keys is stored in the `.env` file, while regular configuration parameters are kept in `config.json`.

## Usage

### Main Workflow

Run the main module to process bookmarks, download new articles, extract text for summarization, tag articles, automatically generate reading lists, and update your article lists:

```bash
uv run -m src.main
```

The automatically generated reading lists allow you to easily import article paths into @Voice or other reader apps, streamlining your reading experience.


### Tag-Based Management

Utilize tag-based filtering to search and organize articles. Example usage in Python:

```python
from src.db import searchArticlesByTags

# Search for articles with specific criteria
articles = searchArticlesByTags(
    all_tags=["tag1", "tag2"],   # Must have ALL these tags
    any_tags=["tag3", "tag4"],   # Can have ANY of these tags
    not_any_tags=["tag5"],         # Must NOT have these tags
    readState="unread",            # Filter by read state
    formats=["pdf", "epub"]       # Filter by file formats
)
```

## Reading Lists

One of the core functions of this project is the automatic generation of reading lists. These lists comprise paths to articles that match a set of specified tags and can be imported into various reading tools, including but not limited to @Voice on Android, allowing you to organize your reading based on topics of interest and seamlessly integrate with your preferred reading applications.

Each tag in the configuration is not only a label but comes with a natural language description (configured in `config.json` under the `article_tags` section). This description is used by the language model (LLM) to determine whether a given article should be associated with a particular tag, making tag assignment both dynamic and context-aware.

### Example Tag Configuration

Here's an example of how tags are configured in `config.json`:

```json
"article_tags": {
    "infofi": {
        "description": "Articles about prediction markets or decision markets or futarchy or which mention info-finance or which are about constructing incentive mechanisms to elicit information or using prediction markets for governance or combining prediction markets/prediction competitions and ai/ml/ai agents",
        "use_summary": true
    }
}
```

### Reading List Generation

The system generates reading lists based on tag configurations defined in `config.json`. This functionality is implemented in `src/generateLists.py` through two main functions:

1. `appendToLists()` - Creates lists of articles matching specific tag criteria
2. `modifyListFiles()` - Processes the articles in each list, converting PDFs to EPUBs when possible and prefixing HTML/MHTML files with summaries if configured

## Workflow Examples

### Adding New Articles from Bookmarks

1. Save articles as bookmarks in your browser's bookmark folder (configured in `config.json`)
2. Run the main workflow:
   ```bash
   uv run -m src.main
   ```
3. The system will:
   - Download articles from bookmarks
   - Extract text and generate summaries
   - Tag articles based on content
   - Update reading lists


## Project Structure

- `src/`: Source code directory
  - `main.py`: Main entry point integrating bookmarks, downloading, summarization, tagging, and list generation.
  - `db.py`: Database operations for storing and querying article metadata, summaries, and tags.
  - `articleSummary.py`: Functions for text extraction and AI-powered summarization of articles.
  - `articleTagging.py`: Implements automatic tagging based on article content.
  - `textExtraction.py`: Handles text extraction from various file formats.
  - `generateLists.py`: Generates lists of articles based on tags and other criteria.
  - `search.py`: Implements a CLI tool for searching articles using Boolean queries.
  - `utils.py`: Utility functions for file operations, URL formatting, and configuration management.
  - Other helper modules such as `downloadNewArticles.py`, `convertGitbooks.py`, and `reTitlePDFs.py` for specialized tasks.

- `storage/`: SQLite database and other persistent storage files.
- `output/`: Generated output files such as search results.
- `logs/`: Application logs including summaries and error logs.

## Configuration Details

- **Sensitive Information**: Stored in the `.env` file (e.g., API keys).
- **Non-Sensitive Configuration**: Stored in `config.json` (e.g., file paths and procedural settings).
- `article_tags`: Defines the available tags along with their natural language descriptions. These descriptions inform the LLM during article tagging.
- `listToTagMappings`: Specifies how articles should be grouped into reading lists based on tag criteria. This determines which articles appear on which reading lists.
- Other settings include directories for storing articles, bookmarks paths, backup locations, document formats to process, and exclusion rules, ensuring that the system is exactly tailored to your workflow.


## Advanced Configuration

### Custom Tag Rules

You can create complex tag rules using the `listToTagMappings` configuration:

```json
"listToTagMappings": {
    "infofi": {
        "all_tags": [],
        "any_tags": ["infofi"],
        "not_any_tags": []
    }
}
```

This creates a reading list called "infofi" that includes any article with the "infofi" tag.

### Multiple Tag Criteria

You can use multiple tag criteria to create more specific reading lists:

```json
"advanced_topic": {
    "all_tags": ["technical", "research"],
    "any_tags": ["ai", "blockchain"],
    "not_any_tags": ["beginner"]
}
```

This creates a list of technical research articles about AI or blockchain that are not tagged as beginner-level.

## Development

- This project leverages the `uv` tool for running and adding dependencies.
- Use `uv run` to execute the application or run modules.
- Follow best practices in code efficiency, modularity, and security (as demonstrated in the project structure).

## Contributing

Contributions are welcome! Please adhere to the guidelines outlined in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

See the [LICENSE](LICENSE) file for details.
