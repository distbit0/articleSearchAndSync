import utils
from utils import getConfig
import glob
import PyPDF2
import urllib.parse
import traceback


def getPDFFolders():
    pdfFolders = getConfig()["pdfSourceFolders"]
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
        pdfFiles = glob.glob(folder + "/**/*.pdf", recursive=True)
        for pdf in pdfFiles:
            fullFileName = pdf.split("/")[-1]
            pdfFileName = fullFileName.replace(".pdf", "")
            pathBelowBaseFolder = pdf.split(folder)[-1].replace(fullFileName, "")
            newBaseUrl = baseUrl.strip("/") + pathBelowBaseFolder

            if pdfFileName not in alreadyIndexedPDFs:
                indexPDF(pdf, newBaseUrl, pdfFileName, indexSubjectPath)


def indexPDF(pdf, baseUrl, pdfFileName, indexFolderPath):
    pdfText = []
    print("INDEXING: ", pdf)
    try:
        pdfFileObj = open(pdf, "rb")
        pdfReader = PyPDF2.PdfFileReader(pdfFileObj)
        for pageNumber in range(0, pdfReader.numPages):
            pageObj = pdfReader.getPage(pageNumber)
            pdfText.append(pageObj.extractText())
        pdfFileObj.close()
    except PyPDF2.errors.PdfReadError:
        traceback.print_exc()
        print("Error in pdf: ", pdf)
        return
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
