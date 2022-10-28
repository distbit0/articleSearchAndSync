import utils
from utils import getConfig
import glob
import PyPDF2
from pathlib import Path
import urllib.parse


def getPDFFolders():
    pdfFolders = getConfig()["pdfFolders"]
    indexFolders = [
        folder.split("/")[-1]
        for folder in glob.glob(
            utils.getAbsPath("../storage/indexedPDFs") + "/**", recursive=True
        )
    ]
    return pdfFolders, indexFolders


def indexAllPDFFolders(pdfFolders, indexFolders):
    for folder in pdfFolders:
        baseUrl = pdfFolders[folder]["pdfBaseURL"]
        subject = pdfFolders[folder]["subject"]
        indexSubjectPath = utils.getAbsPath("../storage/indexedPDFs/" + subject)
        alreadyIndexedPDFs = []
        if subject in indexFolders:
            alreadyIndexedPDFs = [
                file.split("/")[-1].strip(".txt")
                for file in glob.glob(indexSubjectPath + "/**.txt", recursive=True)
            ]
        else:
            utils.mkdirAndParents(indexSubjectPath)
        pdfFiles = glob.glob(folder + "/**.pdf", recursive=True)
        for pdf in pdfFiles:
            pdfFileName = pdf.split("/")[-1].replace(".pdf", "")
            if pdfFileName not in alreadyIndexedPDFs:
                indexPDF(pdf, baseUrl, pdfFileName, indexSubjectPath)


def indexPDF(pdf, baseUrl, pdfFileName, indexFolderPath):
    pdfText = []
    pdfFileObj = open(pdf, "rb")
    pdfReader = PyPDF2.PdfFileReader(pdfFileObj)
    for pageNumber in range(0, pdfReader.numPages):
        pageObj = pdfReader.getPage(pageNumber)
        pdfText.append(pageObj.extractText())
    pdfFileObj.close()
    urlString = (
        "Snapshot-Content-Location: "
        + baseUrl
        + urllib.parse.quote(pdfFileName + ".pdf")
        + "\n"
    )
    pathString = "PdfFilePath: " + pdf + "\n"
    pdfText = urlString + pathString + "\n".join(pdfText)
    with open(indexFolderPath + "/" + pdfFileName + ".txt", "w") as pdfTextFile:
        pdfTextFile.write(pdfText)


if __name__ == "__main__":
    pdfFolders, indexFolders = getPDFFolders()
    indexAllPDFFolders(pdfFolders, indexFolders)
