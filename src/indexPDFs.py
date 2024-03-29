import utils
from utils import getConfig
import glob
import urllib.parse
from pathlib import Path


def getPDFFolders():
    pdfFolders = getConfig()["pdfSearchFolders"]
    indexFolders = [
        folder.split("/")[-1]
        for folder in glob.glob(utils.getAbsPath("../storage/indexedPDFs") + "/**")
    ]
    print("INDEX FOLDERS: ", indexFolders, "\nPDF FOLDERS: ", pdfFolders)
    return pdfFolders, indexFolders


def indexAllPDFFolders(pdfFolders, indexFolders):
    for folder in pdfFolders:
        subject = pdfFolders[folder]["subject"]
        indexSubjectPath = utils.getAbsPath("../storage/indexedPDFs/" + subject)
        alreadyIndexedPDFs = []
        if subject in indexFolders:
            alreadyIndexedPDFs = [
                file.split("/")[-1].replace(".txt", "")
                for file in glob.glob(indexSubjectPath + "/**.txt", recursive=True)
            ]
        else:
            mkdirAndParents(indexSubjectPath)
        print(folder + "/**/*.pdf")
        pdfFiles = glob.glob(folder + "/**/*.pdf", recursive=True)
        print(
            "PDF FILES: ", len(pdfFiles), " ALREADY INDEXED: ", len(alreadyIndexedPDFs)
        )
        for pdf in pdfFiles:
            fullFileName = pdf.split("/")[-1]
            pdfFileName = fullFileName.replace(".pdf", "")

            if pdfFileName not in alreadyIndexedPDFs:
                indexPDF(pdf, pdfFileName, indexSubjectPath)


def mkdirAndParents(directory):
    Path(directory).mkdir(parents=True, exist_ok=True)


def indexPDF(pdf, pdfFileName, indexFolderPath):
    pdfText = []
    print("INDEXING: ", pdf)
    urlString = "Snapshot-Content-Location: " + pdf + "\n"
    pathString = "PdfFilePath: " + pdf + "\n"
    pdfText = urlString + pathString + utils.getPdfText(pdf)
    with open(
        indexFolderPath + "/" + pdfFileName + ".txt", "w", errors="ignore"
    ) as pdfTextFile:
        pdfTextFile.write(pdfText)


if __name__ == "__main__":
    pdfFolders, indexFolders = getPDFFolders()
    indexAllPDFFolders(pdfFolders, indexFolders)
