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
import openai
import time
import json

### todo: add substring matching after semantic matching. i.e. allow a word to be enforced via being quoted in the search querys
##### kind of like how google search works
## exclude chunks which contain no or very low english content
## perhaps only chunk on double new line
## integrate into search.py and indexPdfs.py


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


def read_processed_files():
    processed_files_path = utils.getAbsPath("../storage/embeddedFileNames.json")
    if not os.path.exists(processed_files_path):
        return {}

    with open(processed_files_path, "r") as file:
        processed_files = json.load(file)

    return processed_files


def update_processed_files(file_name, chunks_for_current_file):
    processed_files_path = utils.getAbsPath("../storage/embeddedFileNames.json")
    processed_files = {}

    if os.path.exists(processed_files_path):
        with open(processed_files_path, "r") as file:
            processed_files = json.load(file)

    processed_files[file_name] = chunks_for_current_file

    with open(processed_files_path, "w") as file:
        json.dump(processed_files, file, indent=4)


def process_batch(batch_chunks, collection):
    chunks = [chunk[2] for chunk in batch_chunks]

    while True:
        try:
            batch_embeddings = openai_ef(chunks)
        except openai.error.RateLimitError as e:
            print(e)
            print("Rate limit reached. Waiting 10 seconds...")
            time.sleep(10)
        else:
            break

    current_file_name = None
    ids = []
    embeddings = []

    for chunk_info, embedding in zip(batch_chunks, batch_embeddings):
        file_name, chunk_id, chunk, chunksForCurrentFile = chunk_info
        if file_name != current_file_name:
            if current_file_name is not None:
                collection.upsert(ids=ids, embeddings=embeddings)
                update_processed_files(current_file_name, chunksForCurrentFile)

            current_file_name = file_name
            ids = []
            embeddings = []

        ids.append(f"{file_name}---++---{chunk_id}")
        embeddings.append(embedding)

    if current_file_name is not None:
        collection.upsert(ids=ids, embeddings=embeddings)
        update_processed_files(current_file_name, chunksForCurrentFile)


def store_embeddings(file_paths):
    # try:
    #     chromaClient.delete_collection(name="articles")
    # except:
    #     pass
    collection = chromaClient.get_or_create_collection(
        name="articles",
        embedding_function=openai_ef,
    )
    processed_files = read_processed_files()

    file_paths = [
        path
        for path in file_paths
        if os.path.basename(path) not in list(processed_files.keys())
    ]

    batch_size = 2000
    batch_chunks = []

    for x, file_path in enumerate(file_paths):
        file_name = os.path.basename(file_path)
        print(f"Processing {file_name}")
        with open(file_path, "r") as file:
            try:
                content = file.read()
            except:
                print("Error reading file", file_path)
                continue

        if "htm" in file_path.split(".")[-1]:
            content = html_to_markdown(content)

        chunks = chunkText(content, getConfig()["maxChunkWordCount"])

        chunksForCurrentFile = len(chunks)
        for i, chunk in enumerate(chunks):
            batch_chunks.append((file_name, i, chunk, chunksForCurrentFile))

            if len(batch_chunks) >= batch_size:
                print(
                    "PROGRESS: " + str(int((x + 1) * 1000 / len(file_paths)) / 10) + "%"
                )
                process_batch(batch_chunks, collection)
                batch_chunks = []

    if batch_chunks:
        print("PROGRESS: " + str(int((x + 1) * 1000 / len(file_paths)) / 10) + "%")
        process_batch(batch_chunks, collection)


def find_similar_articles(query, includedFileNames=None, nResults=20):
    similar_articles = []
    processed_files = read_processed_files()

    collection = chromaClient.get_or_create_collection(
        name="articles",
        embedding_function=openai_ef,
    )
    print("collection length " + str(collection.count()))
    # Embed the query
    query_vector = openai_ef([query])[0]

    results = collection.query(
        query_embeddings=query_vector,
        n_results=nResults * 50,
    )

    # Sort the result ids by distance in ascending order
    sorted_ids = sorted(
        results["ids"][0],
        key=lambda x: results["distances"][0][results["ids"][0].index(x)],
    )
    fileNames = set()
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
    print(find_similar_articles("defi privacy mechanisms", 10))


if __name__ == "__main__":
    modelName = "text-embedding-ada-002"
    chromaClient = chromadb.PersistentClient(path=utils.getAbsPath("../storage/chroma"))
    openai_ef = chromadb.utils.embedding_functions.OpenAIEmbeddingFunction(
        api_key=getConfig()["openaiApiKey"], model_name=modelName
    )
    tokenEncoding = tiktoken.encoding_for_model(modelName)

    # profiler = cProfile.Profile()
    # profiler.enable()

    startTime = time.time()
    test()
    print("Time taken: " + str(time.time() - startTime))

    # profiler.disable()
    # stats = pstats.Stats(profiler)
    # stats.sort_stats(pstats.SortKey.CUMULATIVE)
    # stats.print_stats(10)

    # collectionOld = chromaClient.get_or_create_collection(
    #     name="articles", embedding_function=openai_ef
    # )
    # collectionNew = chromaClient.get_or_create_collection(
    #     name="articles2",
    #     embedding_function=openai_ef,
    #     metadata={"hnsw:search_ef": 1500},
    # )
    # length = collectionOld.count()

    # for i in range(0, length, 100):
    #     batch = collectionOld.get(
    #         include=["metadatas", "documents", "embeddings"], limit=100, offset=i
    #     )
    #     collectionNew.add(
    #         ids=batch["ids"],
    #         documents=batch["documents"],
    #         metadatas=batch["metadatas"],
    #         embeddings=batch["embeddings"],
    #     )
    #     if i % 1000 == 0:
    #         print("PROGRESS: " + str(int((i + 1) * 1000 / length) / 10) + "%")

    # time.sleep(100)
    # print("collection length " + str(collectionNew.count()))

    ## delete the collection2 collection
