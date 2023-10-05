import utils
from utils import getConfig
import os
import glob
import shutil


def removeIllegalChars(pdfTitle):
    illegalChars = getConfig()["illegalFileNameChars"]
    for char in illegalChars:
        pdfTitle = pdfTitle.replace(char, "")

    return pdfTitle


def getPDFTitle(pdfPath):
    pdfTitle = ""
    originalFileName = pdfPath.split("/")[-1]
    pdfTitle = os.popen('pdftitle -p "' + pdfPath + '"').read()
    if (not pdfTitle) or len(pdfTitle) < 4:
        pdfTitle = originalFileName[:-4]
        idType = utils.get_id_type(pdfTitle)
        if idType == "arxiv":
            pdfTitle = utils.getArxivTitle(pdfTitle)
        elif idType == "doi":
            pdfTitle = utils.getDOITitle(pdfTitle)
    else:
        pdfTitle = pdfTitle.strip()

    pdfTitle += ".pdf"

    pdfTitle = removeIllegalChars(pdfTitle)
    return pdfTitle


def reTitlePDF(pdfPath):
    pdfTitle = getPDFTitle(pdfPath)
    newPath = "/".join(pdfPath.split("/")[:-1]) + "/" + pdfTitle
    print(newPath, pdfPath)
    return newPath


def getDocsInFolder(folderPath, formats=["pdf"]):
    docPaths = []
    for filePath in glob.glob(folderPath + "/*", recursive=True):
        if "." not in filePath:
            continue
        isDoc = filePath.lower().split(".")[-1] in formats
        if isDoc:
            docPaths.append(filePath)

    return docPaths


def retitlePDFsInFolder(folderPath):
    pdfPaths = getDocsInFolder(folderPath, formats=["pdf"])
    newPdfPaths = []
    for pdfPath in pdfPaths:
        if pdfPath[-4:] != ".pdf":
            continue
        newPath = reTitlePDF(pdfPath).lstrip(".")
        if newPath not in newPdfPaths:
            newPdfPaths.append(newPath)
            os.rename(pdfPath, newPath)


def retitleAllPDFs():
    PDFFolders = getConfig()["PDFSourceFolders"]
    for folderPath in PDFFolders:
        retitlePDFsInFolder(folderPath)

    return


def moveDocsToTargetFolder():
    docPaths = []
    PDFFolders = getConfig()["PDFSourceFolders"]
    docFormatsToMove = getConfig()["docFormatsToMove"]
    targetFolder = getConfig()["articleFileFolder"]
    for folderPath in PDFFolders:
        docPaths += getDocsInFolder(folderPath, formats=docFormatsToMove)

    print("LEN OF docPath", len(docPaths))
    for docPath in docPaths:
        docName = docPath.split("/")[-1]
        print("Moving", docName, "to", targetFolder, " derived from", docPath)
        shutil.move(docPath, targetFolder + "/" + docName)


if __name__ == "__main__":
    retitleAllPDFs()
    moveDocsToTargetFolder()
