import telebot
import xml.etree.ElementTree as ET
import urllib.request
import datetime
import time

### CONFIG

BOT_TOKEN = ''  # токен бота

ALLOWED_USERS = (11111111,22222222,3333333)  #список разрешенных пользователей (telegram.user.id)

# настройки сервера и библиотек. XML-файлы библиотек обычно лежат по адресу вида 'http://SERVER_IP:32400/library/sections/ID/all, ID обычно идут по порядку. поддерживается только два вида медиа - Movies и Series

PLEX_SERVER_CONFIG = {                            
                      'url':'http://192.168.1.111',   
                      'port':'32400',
                      'libraries':[{
                                     'name' : 'ФИЛЬМЫ',
                                     'type' : 'movies',
                                     'id' : '1'
                                   },
                                   {
                                     'name' : 'СEРИАЛЫ',
                                     'type' : 'series',
                                     'id' : '2'
                                   },
                                   {
                                     'name' : 'МУЛЬФИЛЬМЫ',
                                     'type' : 'movies',
                                     'id' : '3'
                                   },
                                   {
                                     'name' : 'МУЛЬТСЕРИАЛЫ',
                                     'type' : 'series',
                                     'id' : '4'
                                   },
                                   {
                                     'name' : 'ДОКУМЕНТАЛКИ',
                                     'type' : 'series',
                                     'id' : '8'}]
                                   }

FRESH_DAYS = 14  #сколько дней должно пройти, чтобы медиа перестало считаться новым

### FUNCTIONS

libRoots = {}

def load_and_parse ():
    for library in PLEX_SERVER_CONFIG['libraries']:
        url = PLEX_SERVER_CONFIG['url'] + ":" + PLEX_SERVER_CONFIG['port'] + "/library/sections/" + library['id'] + "/all"
        urlHandle = urllib.request.urlopen(url)
        parsedHandle = ET.parse(urlHandle)
        libRoots[str(library['name'])] = parsedHandle.getroot()

def split_str(seq, chunk, skip_tail=False):
    lst = []
    if chunk <= len(seq):
        lst.extend([seq[:chunk]])
        lst.extend(split_str(seq[chunk:], chunk, skip_tail))
    elif not skip_tail and seq:
        lst.extend([seq])
    return lst

def log_request(message):
    with open("plexbot.log", "a") as logfile:
        logfile.write(str(message.chat.id) + " " + str(datetime.datetime.now()) + ": " +  str(message.text) + "\n")

def get_all(freshness=10000):
    i = 0
    replyString = ""
    freshness = freshness*24*60*60
    for lib in libRoots:
        library = PLEX_SERVER_CONFIG['libraries'][i]
        replyString = replyString + "\n" + library['name']  + ":" + "\n"
        if library['type'] == "movies":
           counter = 0
           for child in libRoots[lib].iter('Video'):
              if (int(time.time()) - freshness) <= int(child.attrib['addedAt']):
                 counter += 1
                 replyString = replyString + str(counter) + '. ' + child.attrib['title'] + ' (' + child.attrib['year'] + ')' + "\n"
        else:
           for child in libRoots[lib].iter('Directory'):
              if (int(time.time()) - freshness) <= int(child.attrib['addedAt']):
                 counter += 1
                 replyString = replyString + str(counter) + '. ' + child.attrib['title'] + ' (' +  child.attrib['childCount'] + ' сезонов, '  + child.attrib['leafCount']+ ' серий)' + "\n"
        if counter == 0:
                 replyString = replyString + 'Ничего не найдено\n'
        i += 1
        counter = 0
    return(replyString)

## BOT ACTIONS

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(func=lambda message: message.chat.id not in ALLOWED_USERS)
def auth_failed(message):
        bot.send_message(message.chat.id, "Доступ запрещен. Попросите администратора бота добавить вас в белый лист")
        log_request(message)

@bot.message_handler(commands=['start'])
def send_welcome(message):
        bot.reply_to(message, "Алоха! Жми на кнопку МЕНЮ внизу и выбирай команду")


@bot.message_handler(commands=['new'])
def list_new(message):
        load_and_parse()
        for part in split_str(get_all(FRESH_DAYS), 4080):
            bot.send_message(message.chat.id, part)

@bot.message_handler(commands=['list'])
def list_all(message):
        load_and_parse()
        for part in split_str(get_all(), 4080):
            bot.send_message(message.chat.id, part)

@bot.message_handler(content_types=['text'])
def search_command(message):
    if message.text == '/search':
        msg = bot.send_message(message.from_user.id, 'Введите поисковый запрос: ')
        bot.register_next_step_handler(msg, search_by_string)

def search_by_string(message):
    load_and_parse()
    searchString = message.text.replace('ё', 'е')
    i = 0
    replyString = ""
    for lib in libRoots:
        library = PLEX_SERVER_CONFIG['libraries'][i]
        replyString = replyString + "\n" + library['name']  + ":" + "\n"
        if library['type'] == "movies":
           counter = 0
           for child in libRoots[lib].iter('Video'):
              if searchString.casefold() in child.attrib['title'].replace('ё', 'е').casefold():
                 counter += 1
                 replyString = replyString + str(counter) + '. ' + child.attrib['title'] + ' (' + child.attrib['year'] + ')' + "\n"
        else:
           for child in libRoots[lib].iter('Directory'):
              if searchString.casefold() in child.attrib['title'].replace('ё', 'е').casefold():
                 counter += 1
                 replyString = replyString + str(counter) + '. ' + child.attrib['title'] + ' (' +  child.attrib['childCount'] + ' сезонов, '  + child.attrib['leafCount']+ ' серий)' + "\n"
        if counter == 0:
                 replyString = replyString + 'Ничего не найдено\n'
        i += 1
        counter = 0

    for part in split_str(replyString, 4080):
        bot.send_message(message.chat.id, part)

bot.infinity_polling()
