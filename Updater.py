import wikipedia
from html.parser import HTMLParser

class MovieHTMLParser(HTMLParser):

    parsedData = []
    currentData = ''
    
    inHeader = False
    inLink = False
    isList = False
    isItem = False

    skip = False
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.inLink = True
        elif tag == 'li':
            self.isItem = True
        elif tag == 'ul':
            self.isList = True
        elif tag == 'h2' or tag == 'h3':
            self.inHeader = True
            
        for attr in attrs:
            if attr[0] == 'class' and (attr[1] == 'mw-editsection' or attr[1] == 'mw-editsection-bracket'):
                self.skip = True
        #print("Encountered a start tag:", tag)

    def handle_endtag(self, tag):
        if tag == 'a':
            self.inLink = False
        elif tag == 'li':
            self.isItem = False
        elif tag == 'ul':
            self.isList = False
        elif tag == 'h2' or tag == 'h3':
            self.inHeader = False

        if not self.inHeader and not self.inLink and not self.isList and not self.isItem:
            if len(self.currentData) != 0:
                self.parsedData.append(self.currentData)
                self.currentData = ''
        # print("Encountered an end tag :", tag)

    def handle_data(self, data):
        if self.skip or data == 'edit':
            self.skip = False
            return
        
        if self.inHeader:
            self.currentData += data
            #print("Encountered some data  :", data)
            
class TVHTMLParser(HTMLParser):

    parsedData = []
    currentData = ''
    
    inHeader = False
    inLink = False
    isList = False
    isItem = False
    isItalics = False

    skip = False
    
    targetItalicsText = 'Star Trek'
    inTargetHeader = False
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.inLink = True
        elif tag == 'li':
            self.isItem = True
        elif tag == 'ul':
            self.isList = True
        elif tag == 'i':
            self.isItalics = True
        elif tag == 'h1' or tag == 'h2' or tag == 'h3':
            self.inHeader = True
            
        for attr in attrs:
            if attr[0] == 'class' and (attr[1] == 'mw-editsection' or attr[1] == 'mw-editsection-bracket'):
                self.skip = True
        #print("Encountered a start tag:", tag)

    def handle_endtag(self, tag):
        if tag == 'a':
            self.inLink = False
        elif tag == 'li':
            self.isItem = False
        elif tag == 'ul':
            self.isList = False
        elif tag == 'i':
            self.isItalics = False
        elif tag == 'h2' or tag == 'h3':
            self.inHeader = False

        if self.isList and not self.isItem:
            if len(self.currentData) != 0:
                self.parsedData.append(self.currentData)
                self.currentData = ''
        # print("Encountered an end tag :", tag)

    def handle_data(self, data):
        if self.skip or data == 'edit':
            self.skip = False
            return
        
        if self.isList and self.isItem and self.inTargetHeader:
            self.currentData += data
            #print("Encountered some data  :", data)

        if not self.isList and self.isItalics:
            #print("Encountered some data  :", data)
            if data == self.targetItalicsText:
                self.inTargetHeader = True
            else:
                self.inTargetHeader = False
            
                
class HTMLTableParser(HTMLParser):

    parsedData = []
    currentRow = []
    currentData = ''
    
    inHeader = False
    inLink = False
    inTable = False
    inRow = False
    inDivider = False
    inTableHeader = False

    skip = False

    targetHeader = 'Episodes'
    inTargetHeader = False

    foundHorizontalRule = False
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.inLink = True
        elif tag == 'tbody':
            self.inTable = True
        elif tag == 'tr':
            self.inRow = True
        elif tag == 'th':
            self.inTableHeader = True
        elif tag == 'td':
            self.inDivider = True
        elif tag == 'hr':
            self.foundHorizontalRule = True
        elif tag == 'h2':
            self.inHeader = True
            self.inTargetHeader = False

    def handle_endtag(self, tag):
        if tag == 'a':
            self.inLink = False
        elif tag == 'tbody':
            self.inTable = False
        elif tag == 'tr':
            self.inRow = False
        elif tag == 'th':
            self.inTableHeader = False
        elif tag == 'td':
            self.inDivider = False
        elif tag == 'h2':
            self.inHeader = False

        if self.inRow and not self.inDivider and not self.inTableHeader and not self.inLink:
            if len(self.currentData) != 0:
                self.currentRow.append(self.currentData)
                self.currentData = ''

        if not self.inRow and self.inTable:
            if len(self.currentRow) != 0:
                self.parsedData.append(self.currentRow)
                self.currentRow = []
        # print("Encountered an end tag :", tag)

    def handle_data(self, data):
        if self.skip or data == 'edit' or data.startswith('[') or data.endswith(']'):
            self.skip = False
            return
        
        if self.inTable and self.inRow and (self.inTableHeader or self.inDivider or self.inLink) and (len(self.targetHeader) == 0 or (len(self.targetHeader) != 0 and self.inTargetHeader)):
            
            # Usually implies that there's multiple rows (Like if an episode is treated as two)
            if(self.foundHorizontalRule):
                self.currentData += '~'
                self.foundHorizontalRule = False
                
            self.currentData += data
            #print("Encountered some data  :", data)
        
        if not self.inTable and self.inHeader:
            if data == self.targetHeader:
                self.inTargetHeader = True

try:

    TVShows = []
    MovieEras = []
    Movies = []

    rawShows = []
    rawMovies = []

    movieParser = MovieHTMLParser()
    episodeParser = TVHTMLParser()
    tableParser = HTMLTableParser()
    
    # Get direct references to the episode & films lists
    for mediaLists in list(filter(lambda x: 'star trek films' in x.lower() or 'star trek episodes' in x.lower(), wikipedia.page("Star Trek", auto_suggest=False).links)):
        # Get & Parse HTML pages for their lists
        print('Getting '+mediaLists)
##        if 'episode' in mediaLists:
##            episodeParser.feed(wikipedia.page(mediaLists, auto_suggest=False).html())
##            for episodeLists in list(filter(lambda x: 'episodes' in x.lower() and 'list' in x.lower(), episodeParser.parsedData)):
##                print('parsing '+episodeLists)
##                tableParser.feed(wikipedia.page(episodeLists, auto_suggest=False).html())
##                rawShows.append({ episodeLists[episodeLists.index(':')+2:episodeLists.index('episodes')-1] : tableParser.parsedData })
##        else:
        if True:
            print('parsing '+mediaLists)
            movieParser.feed(wikipedia.page(mediaLists, auto_suggest=False).html())
            rawMovies.append(movieParser.parsedData)

    categorie = ''
    movieList = []
    for movieKey in rawMovies:
        if '(' in movieKey and len(categorie) != 0:
            if categorie not in MovieEras:
                MovieEras.append(categorie)
            movieList.append(movieKey)
        else:
            if len(movieList) != 0:
                Movies.append({ categorie : movieList })
                movieList = []
            categorie = movieKey
    
    for showKeys in rawShows:
        #print(showKeys)
        for shows, showEpisodes in showKeys.items():
            #print(showEpisodes)
            numberInFirstCol = False
            tableLength = 0

            season = []
            
            seasonNo = 0
            partNo = 0
                    
            episodeNoOverall = 0
            episodeNoInSeason = 0
            
            for episodeRow in showEpisodes:
                #print(episodeRow)
                
                # Skip if the first row doen't have 'Title' or 'No.' in the first table header use that to determine how many columns to expect
                if 'title' in episodeRow[0].lower() or 'no.' in episodeRow[0].lower():
                    numberInFirstCol = 'no.' in episodeRow[0].lower()
                    tableLength = len(episodeRow)
                elif tableLength is len(episodeRow):

                    episodeName = ''
                    
                    insertAsAnotherEpisode = False
                    dividerIndex = 0
                    
                    noInSeasonHasDivider = False
                    noInSeasonDividerIndex = 0
                    
                    if numberInFirstCol:
                         #   episodeNoInSeason = int(episodeRow[1]) # converting to ints might be an issue if season numbers have decimals
                        if episodeRow[1].isnumeric():
                            # some episodes are counted as multiple (by using an <hr> tag or '-')
                            if '~' in episodeRow[0]: # we substitute an <hr> tag for a tilde when parsing
                                insertAsAnotherEpisode = True
                                dividerIndex = episodeRow[0].index('~')
                            elif '–' in episodeRow[0]:
                                insertAsAnotherEpisode = True
                                dividerIndex = episodeRow[0].index('–')
                            elif '-' in episodeRow[0]:
                                insertAsAnotherEpisode = True
                                dividerIndex = episodeRow[0].index('-')

                            # sometimes the No. Overall has a redundant divider
                            if '~' in episodeRow[1]: # we substitute an <hr> tag for a tilde when parsing
                                noInSeasonHasDivider = True
                                noInSeasonDividerIndex = episodeRow[1].index('~')
                            elif '–' in episodeRow[1]:
                                noInSeasonHasDivider = True
                                noInSeasonDividerIndex = episodeRow[1].index('–')
                            elif '–' in episodeRow[1]:
                                noInSeasonHasDivider = True
                                noInSeasonDividerIndex = episodeRow[1].index('–')

                            #if episodeRow[0].isnumeric():
                            if noInSeasonHasDivider:
                                episodeNoInSeason = int(episodeRow[1][:noInSeasonDividerIndex]) # converting to ints might be an issue if season numbers have decimals
                            else:
                                episodeNoInSeason = int(episodeRow[1])


                            if insertAsAnotherEpisode:
                                episodeNoOverall = int(episodeRow[0][:dividerIndex]) # converting to ints might be an issue if episode numbers have decimals
                            else:
                                episodeNoOverall = int(episodeRow[0])

                            episodeName = episodeRow[2]
                        else:
                            # if there's only one number column
                            if '~' in episodeRow[0]: # we substitute an <hr> tag for a tilde when parsing
                                insertAsAnotherEpisode = True
                                noInSeasonDividerIndex = episodeRow[0].index('~')
                            elif '–' in episodeRow[0]:
                                insertAsAnotherEpisode = True
                                noInSeasonDividerIndex = episodeRow[0].index('–')
                            elif '-' in episodeRow[0]:
                                insertAsAnotherEpisode = True
                                noInSeasonDividerIndex = episodeRow[0].index('-')
                                
                            if insertAsAnotherEpisode:
                                episodeNoInSeason = int(episodeRow[0][:noInSeasonDividerIndex]) # converting to ints might be an issue if episode numbers have decimals
                            else:
                                episodeNoInSeason = int(episodeRow[0])

                            seasonNo = 1; # a single 'no.' column indicates that there has only been one season
                            
                            episodeName = episodeRow[1]
                    # if first column doesn't have a number then it's a pilot 'season' or 'season 0'
                    else:
                        episodeNoInSeason = 1
                        episodeNoOverall = 0;
                        episodeName = episodeRow[0]

                    #print(episodeName)
                    
                    # if this is a new season
                    if episodeNoOverall >= episodeNoInSeason and episodeNoInSeason == 1:
                        seasonNo=seasonNo+1;

                    # string replacements
                    episodeName = episodeName.replace("\\","",5)
                    episodeName = episodeName.replace("\"","",6)
                    episodeName = episodeName.replace("\xa0"," ",6)
                    
                    if insertAsAnotherEpisode:
                        season.append("S"+str(seasonNo)+"E"+str(episodeNoInSeason).zfill(2)+" "+episodeName+" Part I")
                        season.append("S"+str(seasonNo)+"E"+str(episodeNoInSeason+1).zfill(2)+" "+episodeName+" Part II")
                        episodeNoInSeason = episodeNoInSeason+2
                        episodeNoOverall = episodeNoOverall+2
                    else:
                        season.append("S"+str(seasonNo)+"E"+str(episodeNoInSeason).zfill(2)+" "+episodeName)
                        episodeNoInSeason = episodeNoInSeason+1
                        episodeNoOverall = episodeNoOverall+1



            # when done add it to list of TVShows
            if len(season) != 0:
                #print(season)
                TVShows.append({ shows : season })
                season = []

    #for show in TVShows:
    #    print(show)
    
    # TODO: clean up the data and create lists within lists 
    for movie in Movies:
        print(movie)
            
    # Find in the python script where the arrays are and overwrite them
    #file = open("StarTrekEpisodeAndMoviePicker.py", "rt")
    #script = file.read()
    #file.close()

    # for each movie era -> movies and tv shows -> episode ((eras * movies) + (series * episodes)) 
    for media in [MovieEras, TVShows]:
        for mediaPeices in media:
            # Create shortening using key name
            for categorie, mediaPeice in mediaPeices.items():
                print(mediaPeice)
                    # iterate through each line to find the location of the shortenedName
                    #for line in data:
                        #if we found the variables remember the index and find the end of it
                        #Update mapping array (Find the variable, then the end point.)
                    
        #Update label array (in first loop)
    
    
    
except BaseException as err:
    print(f"Unexpected {err=}, {type(err)=}")
    raise
