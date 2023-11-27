import telebot
import xml.etree.ElementTree as ET
import urllib.request
import time

urlHandleMovies = urllib.request.urlopen("http://192.168.1.111:32400/library/sections/1/all") # URL OF THE PLEX MOVIES LIST
urlHandleSeries = urllib.request.urlopen("http://192.168.1.111:32400/library/sections/2/all") # URL OF THE PLEX TV SERIES LIST

keyboard1 = telebot.types.ReplyKeyboardMarkup(True)
keyboard1.row('Back')

def split_str(seq, chunk, skip_tail=False):  ### LONG STRING SPLITTER FOR TELEGRAM MESSAGES
    lst = []
    if chunk <= len(seq):
        lst.extend([seq[:chunk]])
        lst.extend(split_str(seq[chunk:], chunk, skip_tail))
    elif not skip_tail and seq:
        lst.extend([seq])
    return lst

treeMovies = ET.parse(urlHandleMovies)
rootMovies = treeMovies.getroot()
treeSeries = ET.parse(urlHandleSeries)
rootSeries = treeSeries.getroot()

token = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX' # TELEGRAM TOKEN FOR YOUR BOT

bot = telebot.TeleBot(token)

@bot.message_handler(commands=['start'])
def send_welcome(message):
        bot.reply_to(message, "Hi! Select a command from the menu below")

@bot.message_handler(commands=['new'])  ### BOT RESPONSE TO THE \new COMMAND
def send_new(message):
        cntNewMovies = 0
        cntNewSeries = 0
        replyStringNewMovies = '~~~ MEW MOVIES (ADDED IN LAST 14 DAYS) ~~~' + '\n'
        replyStringNewSeries = '~~~ NEW SERIES (ADDED IN LAST 14 DAYS) ~~~' + '\n'
        for child in rootMovies.iter('Video'):
              if (time.time() - int(child.attrib['addedAt']) <= 1209600):  ### 14 DAYS IN SECONDS
                 cntNewMovies += 1
                 replyStringNewMovies = replyStringNewMovies + str(cntNewMovies) + '. ' + child.attrib['title'] + ' ('+ child.attrib['year']+ ')' + "\n"
        if cntNewMovies == 0:
                 replyStringNewMovies =  'No new movies'
        for part in split_str(replyStringNewMovies, 4090):
             bot.reply_to(message, part)
        for child in rootSeries.iter('Directory'):
              if (time.time() - int(child.attrib['addedAt']) <= 1209600):
                 cntNewSeries += 1
                 replyStringNewSeries = replyStringNewSeries + str(cntNewSeries) + '. ' + child.attrib['title'] + ' ('+ child.attrib['year']+ ')' + "\n"
        if cntNewSeries == 0:
                 replyStringNewSeries =  'Now new series'
        for part in split_str(replyStringNewSeries, 4090):
             bot.reply_to(message, part)


@bot.message_handler(commands=['list'])  ### BOT RESPONSE TO THE \list COMMAND
def list_command(message):
        cntMovies = 0
        cntSeries = 0
        replyStringMovies = '~~~ ALL MOVIES ~~~' + '\n'
        replyStringSeries = '~~~ ALL SERIES ~~~' + '\n'
        for child in rootMovies.iter('Video'):
              cntMovies += 1
              replyStringMovies = replyStringMovies + str(cntMovies) + '. ' + child.attrib['title'] + ' ('+ child.attrib['year']+ ')' + "\n"
        for part in split_str(replyStringMovies, 4090):
             bot.reply_to(message, part)
        for child in rootSeries.iter('Directory'):
                 cntSeries += 1
                 replyStringSeries = replyStringSeries + str(cntSeries) + '. ' + child.attrib['title'] + ' (' + child.attrib['childCount'] + ' seasons, '  + child.attrib['leafCount']+ ' episodes)' + "\n"
        for part in split_str(replyStringSeries, 4090):
             bot.reply_to(message, part)

@bot.message_handler(content_types=['text']) ### BOT RESPONSE TO THE \search COMMAND
def search_command(message):
    if message.text == '/search':
        msg = bot.send_message(message.from_user.id, 'Search string: ', reply_markup = keyboard1)
        bot.register_next_step_handler(msg, search_by_string)

def search_by_string(message):
        cntFoundMovies = 0
        cntFoundSeries = 0
        replyStringFoundMovies = '~~~ FOUND IN MOVIES ~~~' + '\n'
        replyStringFoundSeries = '~~~ FOUND IN SERIES ~~~' + '\n'
        for child in rootMovies.iter('Video'):
              if searchString.casefold() in child.attrib['title'].casefold():
                 cntFoundMovies += 1
                 replyStringFoundMovies = replyStringFoundMovies + str(cntFoundMovies) + '. ' + child.attrib['title'] + ' ('+ child.attrib['year']+ ')' + '\n'
        if cntFoundMovies == 0: 
                 replyStringFoundMovies =  'No movies found' 
        for part in split_str(replyStringFoundMovies, 4090):
             bot.reply_to(message, part)
        for child in rootSeries.iter('Directory'):
              if searchString.casefold() in child.attrib['title'].casefold():
                 cntFoundSeries += 1
                 replyStringFoundSeries = replyStringFoundSeries + str(cntFoundSeries) + '. ' + child.attrib['title']  + ' (' + child.attrib['childCount'] + ' seasons, '  + child.attrib['leafCount']+ ' episodes)' + "\n"
        if cntFoundSeries == 0:
                 replyStringFoundSeries =  'No series found'
        for part in split_str(replyStringFoundSeries, 4090):
             bot.reply_to(message, part)

bot.infinity_polling()




