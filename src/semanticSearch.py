from utils import getConfig
from markdownify import markdownify as md
import glob
import utils
import cProfile, pstats
import os
import chromadb
from inscriptis import get_text
import search
import tiktoken

### todo: add substring matching after semantic matching
#  support pdfs, epub and mobi without including html or pdf metadata and tags


client = chromadb.PersistentClient(path=utils.getAbsPath("../data/chroma"))
openai_ef = chromadb.utils.embedding_functions.OpenAIEmbeddingFunction(
    api_key=getConfig()["openaiApiKey"], model_name="text-embedding-ada-002"
)
tokenEncoding = tiktoken.encoding_for_model("text-embedding-ada-002")


def chunkText(input_string, max_length):
    newLineCount = input_string.count("\n")
    print("newLineCount: " + str(newLineCount))
    print("spaces: " + str(input_string.count(" ")))
    words = input_string.replace("\n", " \n ").split(" ")
    chunks = []
    current_chunk = []

    def appendChunk(chunks, current_chunk):
        chunkText = " ".join(current_chunk).strip()
        chunkTokenLength = len(tokenEncoding.encode(chunkText))
        if (
            chunkTokenLength < max_length * 3
            and len(chunkText) * 7 > len(current_chunk)
            and chunkText != ""
        ):
            chunks.append(chunkText)
        return chunks

    for word in words:
        if "\n" in word and len(current_chunk) >= max_length:
            chunks = appendChunk(chunks, current_chunk)
            current_chunk = [word]
        else:
            current_chunk.append(word)

    if current_chunk:
        chunks = appendChunk(chunks, current_chunk)

    print("Chunks: " + str(len(chunks)))
    return chunks


def html_to_markdown(html_content):
    text = get_text(html_content)
    return text


def create_openai_embeddings(file_path):
    # Load the OpenAIEmbeddings class

    # Read the contents of the file
    with open(file_path, "r") as file:
        content = file.read()

    # Convert HTML to text
    if "htm" in file_path.split(".")[-1]:
        content = html_to_markdown(content)

    # Split the content into 100-word chunks
    chunks = chunkText(content, 200)

    embeddings = openai_ef(chunks)
    return embeddings


def read_processed_files(processed_files_path):
    if not os.path.exists(processed_files_path):
        return set()

    with open(utils.getAbsPath(processed_files_path), "r") as file:
        processed_files = set(file.read().splitlines())
    return processed_files


def update_processed_files(processed_files_path, file_name):
    with open(utils.getAbsPath(processed_files_path), "a") as file:
        file.write(file_name + "\n")


def store_embeddings(file_paths):
    try:
        client.delete_collection(name="articles")
    except:
        pass
    collection = client.get_or_create_collection(
        name="articles", embedding_function=openai_ef
    )
    processed_files_path = utils.getAbsPath("../data/embeddedFileNames.txt")
    processed_files = read_processed_files(processed_files_path)

    for file_path in file_paths[:25]:
        ids = []
        file_name = os.path.basename(file_path)
        if file_name in processed_files:
            pass  # continue  # Skip already processed files

        print(file_path)
        embeddings = create_openai_embeddings(file_path)

        # Store each embedding in Qdrant, linking them to the file name

        for i, embedding in enumerate(embeddings):
            ids.append(file_name + "---++---" + str(i))

        collection.upsert(ids=ids, embeddings=embeddings)

        # Update the list of processed files
        update_processed_files(processed_files_path, file_name)


def find_similar_articles(query, nResults=20):
    similar_articles = []
    collection = client.get_or_create_collection(
        name="articles", embedding_function=openai_ef
    )
    # Embed the query
    query_vector = openai_ef([query])[0]

    results = collection.query(
        query_embeddings=query_vector,
        n_results=nResults * 50,
    )
    fileNames = set()

    # Sort the result ids by distance in ascending order
    sorted_ids = sorted(
        results["ids"][0],
        key=lambda x: results["distances"][0][results["ids"][0].index(x)],
    )

    for id in sorted_ids:
        # Split the id to get the actual id
        fileName = id.split("---++---")[0]
        distance = results["distances"][0][results["ids"][0].index(id)]
        if fileName in fileNames:
            continue
        fileNames.add(fileName)
        similar_articles.append((fileName, distance))
        if len(fileNames) == nResults:
            break

    return similar_articles


def test():
    articleFilePattern = getConfig()["articleFilePattern"]
    articleFileFolder = getConfig()["articleFileFolder"]
    articlePathPattern = articleFileFolder + articleFilePattern
    allArticlesPaths = glob.glob(articlePathPattern, recursive=True)
    textToPdfFileMap = search.getPDFPathMappings()
    allArticlesPaths.extend(textToPdfFileMap)
    # store_embeddings(allArticlesPaths)
    print(find_similar_articles("perpetual swaps", 10))


test()
