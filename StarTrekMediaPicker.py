import json
import os
import random
import time
import webbrowser

random.seed(time.time())

# Episode and movie data lives in data.json, maintained by Updater.py.
# Keeping the data out of this script means an updater run can never corrupt
# the program logic -- it only ever rewrites the JSON file.
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

try:
    with open(DATA_FILE, encoding="utf-8") as _data_file:
        _data = json.load(_data_file)
except FileNotFoundError:
    raise SystemExit("data.json not found -- run Updater.py to generate it.")
except (ValueError, KeyError) as _err:
    raise SystemExit("data.json is invalid (%s) -- re-run Updater.py." % _err)

# Menu labels and the index -> media mappings used by the picker loop below.
series = [show["label"] for show in _data["series"]]
movieSeries = [era["label"] for era in _data["movies"]]
TVMapping = {index: show["episodes"] for index, show in enumerate(_data["series"])}
MovieMapping = {index: era["films"] for index, era in enumerate(_data["movies"])}

while(True):
    print("\n"+
          "\t               .\n"+
          "\t              .:.\n"+
          "\t             .:::.\n"+
          "\t            .:::::.\n"+
          "\t        ***.:::::::.***\n"+
          "\t   *******.:::::::::.*******\n"+
          "\t ********.:::::::::::.********\n"+
          "\t********.:::::::::::::.********\n"+
          "\t*******.::::::\'***`::::.*******\n"+
          "\t******.::::\'*********`::.******\n"+
          "\t ****.:::\'*************`:.****\n"+
          "\t   *.::\'*****************`.*\n"+
          "\t   .:\'  ***************    .\n"+
          "\t  .\n"+
          "\t\n"+
          "\t\n"+
          "\tRandom Star Trek Media Picker")

    typeMedia = ''
    while(len(typeMedia) == 0):
        typeMedia = input('\n( 1 ) TV Shows\n( 2 ) Movies\n( 3 ) I\'m Feeling Lucky\n( 4 ) Quit\n\n> ')

    typeMedia = int(typeMedia)

    if(typeMedia == 4):
      exit()

    show = ''

    if(typeMedia == 3):
      show = '-1'

    while(len(show) == 0):
        count = 0
        print('')
        if(typeMedia == 1):
          for showtype in series:
              print('(',count,') ',showtype)
              count+=1
          show = input('\nWhich shows? > ')
        else:
          for showtype in movieSeries:
              print('(',count,') ',showtype)
              count+=1
          show = input('\nWhich films? > ')

        if(len(str(show)) == 0):
            typeMedia = ''
            break

    if(len(str(show)) == 0):
        continue

    show = int(show)
    repeat = ''
    # Seeded before the loop so the browser-search branch (repeat == 3), which
    # skips the pick block and reuses the previous result, always has a value.
    resultIsEpisode = False
    while(len(str(repeat)) == 0 or repeat == 1 or repeat == 3):
        result = ''
        if(repeat != 3):
          if(typeMedia == 1):
              targetArr = TVMapping.get(show)
              result = targetArr[random.randint(0,len(targetArr)-1)]
              resultName = series[show]
              resultIsEpisode = True
              print('\n  ',resultName)
              print('\n\t',result)
          elif(typeMedia == 3):
              mappingIndex = random.randint(0,1)
              targetMapping = TVMapping if mappingIndex == 0 else MovieMapping
              selectedMapping = random.randint(0,len(targetMapping)-1)
              targetShow = targetMapping[selectedMapping]
              result = targetShow[random.randint(0,len(targetShow)-1)]
              resultName = (series if mappingIndex == 0 else movieSeries)[selectedMapping]
              resultIsEpisode = mappingIndex == 0
              print('\n  ',resultName)
              print('\n\t',result)
          else:
              targetArr = MovieMapping.get(show)
              result = targetArr[random.randint(0,len(targetArr)-1)]
              resultName = movieSeries[show]
              resultIsEpisode = False
              print('\n  ',resultName)
              print('\n\t',result)

        if(typeMedia == 3):
            repeat = input('\n( 1 ) I\'m Feeling Lucky\n( 2 ) Return to Menu\n( 3 ) Open in Browser\n( 4 ) Open in Browser and Close\n( 5 ) Quit\n\n> ')
        else:
            repeat = input('\n( 1 ) I\'m Feeling Lucky ('+resultName+')\n( 2 ) Return to Menu\n( 3 ) Open in Browser\n( 4 ) Open in Browser and Close\n( 5 ) Quit\n\n> ')
        
        repeat = int(repeat)

        if(repeat == 5):
            exit()

        if(repeat == 3 or repeat == 4):
          # Prefix the series name so the search finds the right episode;
          # film titles are already complete, so they are searched as-is.
          query = (resultName+' '+result) if resultIsEpisode else result
          webbrowser.open_new_tab('https://www.google.com/search?q='+query.replace(' ','+'))
          if(repeat == 4):
            exit()
