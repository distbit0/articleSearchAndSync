import utils

subject = "machine and human"


def getBlogs(subject):
    urls = utils.getUrlsInLists(subject)
    blogs = utils.getBlogsFromUrls(urls)
    return blogs


def getOnlyNewBlogs(blogs):
    newBlogs = []
    alreadyReviewedBlogs = utils.getUrlsFromFile(
        utils.getAbsPath("../storage/reviewedBlogs.txt")
    )
    for blog in blogs:
        if not blog in alreadyReviewedBlogs:
            newBlogs.append(blog)

    return newBlogs


if __name__ == "__main__":
    blogs = getBlogs(subject)
    newBlogs = getOnlyNewBlogs(blogs)
    newBlogs = [blog.replace("scribe.rip", "medium.com") for blog in newBlogs]
    print("\n".join(sorted(list(set(newBlogs)))))
    addBlogs = input("Add blogs to reviewed? (default=no): ")
    if addBlogs.lower() in ["y", "yes"]:
        utils.addUrlToUrlFile(
            newBlogs, utils.getAbsPath("../storage/reviewedBlogs.txt")
        )
