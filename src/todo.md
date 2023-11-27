 todo searchArticlesForQuery
- [ ] check whether the uses require only files from a certain dir (path argument)
- [ ] check whether the uses require only files with certain extensions (e.g. html) (otherwise no articles will be returned)
    - [ ] sometimes use docFormatsToMove = getConfig()["docFormatsToMove"]  
- [ ] determine whether they want file names to be mapped to urls
- [ ] determine whether they assume urls will be valid and whether they check url validity
- [ ] check whether these functions want the original article path or the indexed article path (for pdfs)
- [ ] check that they pass subjects and formats as a list
- [ ] use list() around .values() or .keys()














 todo getArticlePathsForQuery
- [ ] check whether the uses require only files from a certain dir (path argument)
- [ ] check whether the uses require only files with certain extensions (e.g. html) (otherwise no articles will be returned)
    - [ ] sometimes use docFormatsToMove = getConfig()["docFormatsToMove"]  
- [ ] check that they pass formats as a list