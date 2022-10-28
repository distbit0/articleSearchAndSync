import os

rootdir = "/home/pimania/Syncs/@Voice/"
rlstDir = "/home/pimania/Syncs/@Voice/.config/"
subject = "Ethereum"
folderName = "_" + subject
rlstFile = rlstDir + subject + ".rlst"


editedFile = []
rlstContents = open(rlstFile).read()
i = 0
for line in rlstContents.split("\n"):
    if line.startswith(folderName):
        filePath = line.strip().split("html")[0].strip()
        if not filePath.endswith("html"):
            filePath += "html"
        fullFilePath = rootdir + filePath
        if not os.path.isfile(fullFilePath):
            print(fullFilePath)
            i += 1
        else:
            editedFile.append(line)
    else:
        editedFile.append(line)


with open(rlstFile, "w") as rlstFileObj:
    rlstFileObj.write("\n".join(editedFile).strip())
