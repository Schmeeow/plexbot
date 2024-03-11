"""
SimPlexBot
"""

import xml.etree.ElementTree
import urllib.request
import time
import telebot

###  НАСТРОЙКИ

BOT_TOKEN = '' # TG токен бота

ALLOWED_USERS = (11111111,222222222,3333333333) # TG ID разрешенных пользователей

# Настройки сервера и библиотек. XML-файлы библиотек обычно лежат по адресу
# вида 'http://SERVER_IP:32400/library/sections/ID/all, ID обычно идут
# по порядку. поддерживается только два вида медиа - Movies и Series

PLEX_SERVER_CONFIG = { 'url':'http://192.168.1.111',
                       'port':'32400',
                       'libraries':[{'name':'ФИЛЬМЫ','id':'1'},
                                    {'name':'СEРИАЛЫ','id':'2'},
                                    {'name':'МУЛЬТФИЛЬМЫ','id':'3'},
                                    {'name':'МУЛЬТСЕРИАЛЫ','id':'4'},
                                    {'name':'ДОКФИЛЬМЫ','id':'10'},
                                    {'name':'ДОКСЕРИАЛЫ','id':'8'}] }

FRESH_DAYS = 14  #сколько дней должно пройти, чтобы медиа перестало считаться новым

### ФУНКЦИИ

lib_roots = {}

def load_and_parse() -> dict:
    """ Грузим XML и преобразуем в деревья """
    for library in PLEX_SERVER_CONFIG['libraries']:
        url = f"{PLEX_SERVER_CONFIG['url']}:{PLEX_SERVER_CONFIG['port']}" \
              f"/library/sections/{library['id']}/all"
        with urllib.request.urlopen(url) as url_handle:
            parsed_handle = xml.etree.ElementTree.parse(url_handle)
        lib_roots[library['name']] = parsed_handle.getroot()

def get_list(freshness = 10000) -> list:
    """ Получаем из библиотек список элементов с заданной свежестью.
    По умолчанию свежесть равна 10000 дням, то есть выводятся все элементы.
    Пустые библиотеки не выводятся """
    load_and_parse()
    results = {}
    freshness = freshness*24*60*60
    best_before = time.time() - freshness
    for lib, content in lib_roots.items():
        items = []
        if content.attrib['viewGroup'] == "movie":
            for child in content.iter('Video'):
                if int(child.attrib['addedAt']) >= best_before:
                    item_desc = f"{child.attrib['title']} ({child.attrib['year']})"
                    items.append(item_desc)
        elif content.attrib['viewGroup'] == "show":
            for child in content.iter('Directory'):
                if int(child.attrib['addedAt']) >= best_before:
                    item_desc = f"{child.attrib['title']} ({child.attrib['childCount']} сезонов, "\
                                f"{child.attrib['leafCount']} серий)"
                    items.append(item_desc)
        if len(items) !=0:
            results[lib] = items
    return results

def search_by_string(message) -> list:
    """ Получаем из библиотек список элементов с совпадениями по поисковой фразе.
    Для пустых библиотек выводим фразу 'Ничего не найдено'. Заодно меняем е на ё """
    load_and_parse()
    found = False
    results = {}
    search_string = message.text.replace('ё', 'е')
    for lib, content in lib_roots.items():
        items = []
        if content.attrib['viewGroup'] == "movie":
            for child in content.iter('Video'):
                if search_string.casefold() in child.attrib['title'].replace('ё', 'е').casefold():
                    item_desc = f"{child.attrib['title']} ({child.attrib['year']})"
                    items.append(item_desc)
                    found = True
        elif content.attrib['viewGroup'] == "show":
            for child in content.iter('Directory'):
                if search_string.casefold() in child.attrib['title'].replace('ё', 'е').casefold():
                    item_desc = f"{child.attrib['title']} ({child.attrib['childCount']} сезонов, "\
                                f"{child.attrib['leafCount']} серий)"
                    items.append(item_desc)
                    found = True
        if len(items) !=0:
            results[lib] = items
    if found is True:
        message_parts = compose_message(results, 100)
        for part in message_parts:
            bot.send_message(message.chat.id, part)
    else:
        bot.send_message(message.chat.id, "К сожалению, ничего не найдено")

def compose_message(results, rows) -> list:
    """ Из результатов поиска по библиотеке формируем сообщения для телеграм
    разбивая их на части из-за ограничения на длину одного сообщения """
    message_parts = []
    for key in results:
        lines = []
        lines.append(f"{key} ({len(results[key])})\n")
        for number, item in enumerate(results[key],1):
            lines.append(f"{number}. {item}\n")
        for i in range(0, len(lines), rows):
            message_parts.append(lines[i:i+rows])
    strings = []
    for part in message_parts:
        strings.append(''.join(part))
    return strings

## БОТ

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(func=lambda message: message.chat.id not in ALLOWED_USERS)
def auth_failed(message):
    """ Проверка пользователя на список допущенных """
    bot.send_message(message.chat.id, 'Доступ запрещен. Попросите добавить вас в белый лист.')

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """ Обработка команды /start """
    bot.reply_to(message, "Привет! Введи текст для поиска или выбери команду в меню")

@bot.message_handler(commands=['new'])
def list_new(message):
    """ Вывод новых элементов по команде /new"""
    results = get_list(FRESH_DAYS)
    message_parts = compose_message(results, 100)
    for part in message_parts:
        bot.send_message(message.chat.id, part)

@bot.message_handler(commands=['list'])
def list_all(message):
    """ Вывод всех элементов по команде /list """
    results = get_list()
    message_parts = compose_message(results, 100)
    for part in message_parts:
        bot.send_message(message.chat.id, part)

@bot.message_handler(content_types=['text'])
def search_command(message):
    """ Поиск по любой текстовой фразе """
    search_by_string(message)

bot.infinity_polling()
