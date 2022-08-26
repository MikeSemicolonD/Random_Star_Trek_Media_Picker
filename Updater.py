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

        if self.isList and not self.isItem:
            if len(self.currentData) != 0:
                self.parsedData.append(self.currentData)
                self.currentData = ''
        # print("Encountered an end tag :", tag)

    def handle_data(self, data):
        if self.skip or data == 'edit':
            self.skip = False
            return
        
        if self.isList and self.isItem:
            self.currentData += data
            #print("Encountered some data  :", data)

class HTMLTableParser(HTMLParser):

    parsedData = []
    currentRow = []
    currentData = ''
    
    inHeader = False
    inLink = False
    inTable = False
    inRow = False
    inDivider = False

    skip = False

    targetHeader = 'Episodes'
    inTargetHeader = False
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.inLink = True
        elif tag == 'tbody':
            self.inTable = True
        elif tag == 'tr':
            self.inRow = True
        elif tag == 'td':
            self.inDivider = True
        elif tag == 'h2':
            self.inHeader = True
            self.inTargetHeader = False
            
        #for attr in attrs:
        #    if attr[0] == 'class' and (attr[1] == 'mw-editsection' or attr[1] == 'mw-editsection-bracket'):
        #        self.skip = True
        #print("Encountered a start tag:", tag)

    def handle_endtag(self, tag):
        if tag == 'a':
            self.inLink = False
        elif tag == 'tbody':
            self.inTable = False
        elif tag == 'tr':
            self.inRow = False
        elif tag == 'td':
            self.inDivider = False
        elif tag == 'h2':
            self.inHeader = False

        if self.inRow and not self.inDivider and not self.inLink:
            if len(self.currentData) != 0:
                self.currentRow.append(self.currentData)
                self.currentData = ''

        if not self.inRow and self.inTable:
            if len(self.currentRow) != 0:
                self.parsedData.append(self.currentRow)
                self.currentRow = []
        # print("Encountered an end tag :", tag)

    def handle_data(self, data):
        if self.skip or data == 'edit':
            self.skip = False
            return
        
        if self.inTable and self.inRow and (self.inDivider or self.inLink) and (len(self.targetHeader) == 0 or (len(self.targetHeader) != 0 and self.inTargetHeader)):
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
        print(mediaLists)
        if 'episode' in mediaLists:
            episodeParser.feed(wikipedia.page(mediaLists, auto_suggest=False).html())
            for episodeLists in episodeParser.parsedData:
                print('parsing '+episodeLists)
                tableParser.feed(wikipedia.page(episodeLists, auto_suggest=False).html())
                rawShows.append({ episodeLists[episodeLists.index(':')+2] : tableParser.parsedData })
        else:
            print('parsing movies')
            movieParser.feed(wikipedia.page(mediaLists, auto_suggest=False).html())
            rawMovies.append(movieParser.parsedData)
    
    for show in rawShows:
        #if first column doesn't have a number then it's a pilot 'season' or 'season 0'
        #else insert episode name (if the number decreased from previous then it's a new season)
        print(part)
        for episodes in show:
            print(episodes)

    
    # TODO: clean up the data and create lists within lists 
    for part in rawMovies:
        print(part)
            
    # Find in the python script where the arrays are and overwrite them
    
    
    
    
    
except BaseException as err:
    print(f"Unexpected {err=}, {type(err)=}")
    raise
