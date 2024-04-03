""" SimPlexBot - телеграм-бот для PLEX (async)"""

import asyncio
import sys
import xml.etree.ElementTree
import urllib.request
import time
import random
import os
import itertools

from aiogram import F, Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import Message, FSInputFile


###  НАСТРОЙКИ

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

FRESH_DAYS = 14  #сколько дней должно пройти, чтобы медиа перестало считаться новый

BLANK_IMAGE = '/web/static/b38a559594ac52d049ba.png' # пустая картинка на том же сервере

TEMP_DIR = 'temp' # временная папка для сохранения картинок

CACHE_TIME = 3 # максимальная частота обновления XML, в минутах


### ФУНКЦИИ


lib_items = {}
last_request_time = 0

async def parse_lib(url, name) -> dict:
    """ Грузим библиотеку, формируем новый словарь, заменяем отсутствующие данные"""   
    try:
        with urllib.request.urlopen(url) as url_handle:
            parsed_handle = xml.etree.ElementTree.parse(url_handle)
    except Exception as error:
        print(f"ERROR: XML-файл не найден по адресу {url}")
        sys.exit(1)
    lib_root = parsed_handle.getroot()
    iterables = itertools.chain(lib_root.iter('Video'),lib_root.iter('Directory')) # фильмы и сериалы
    items = []
    for child in iterables:
        item = {}
        if not 'title' in child.attrib:
            item['title'] = 'Без названия'
        else:
            item['title'] = child.attrib['title']
        if not 'title' in child.attrib:
            item['title'] = 'Без названия'
        else:
            item['title'] = child.attrib['title']
        if not 'summary' in child.attrib:
            item['summary'] = 'Без описания'
        else:
            item['summary'] = child.attrib['summary']
        if 'childCount' in child.attrib:
            item['episodes'] = f"{child.attrib['childCount']} {numeral_text_ending('seasons', child.attrib['childCount'])}, " \
                               f"{child.attrib['leafCount']} {numeral_text_ending('series', child.attrib['leafCount'])}"
        if not 'year' in child.attrib:
            item['year'] = 'XXXX'
        else:
            item['year'] = child.attrib['year']
        if not 'thumb' in child.attrib:
            item['thumb'] = f"{PLEX_SERVER_CONFIG['url']}:{PLEX_SERVER_CONFIG['port']}{BLANK_IMAGE}"
        else:
            item['thumb'] = f"{PLEX_SERVER_CONFIG['url']}:{PLEX_SERVER_CONFIG['port']}{child.attrib['thumb']}"
        if not 'audienceRating' in child.attrib:
            item['rating'] = '---'
        else:
            item['rating'] = child.attrib['audienceRating']
        if not 'title' in child.attrib:
            item['date_added'] = '1262304000' # 1 января 2010, если нет даты добавления
        else:
            item['date_added'] = child.attrib['addedAt']
        items.append(item)
    lib_items[name] = items
    return lib_items[name]


async def load_and_parse() -> dict:
    """ Загружаем все библиотеки """    
    global last_request_time    
    if round(time.time()) - last_request_time >= CACHE_TIME*60: # кэшируем распарсенный XML
        tasks=[]
        for library in PLEX_SERVER_CONFIG['libraries']:
            url = f"{PLEX_SERVER_CONFIG['url']}:{PLEX_SERVER_CONFIG['port']}" \
                  f"/library/sections/{library['id']}/all"
            task = parse_lib(url,library['name'])
            tasks.append(task)
        await asyncio.gather(*tasks)
        last_request_time = round(time.time())
        return lib_items


def numeral_text_ending(text_type, number) -> str:
    """ Подставляем правильное окончание числительных для сезонов или серий """
    season_endings = ['сезонов','сезон',
                      'сезона','сезона',
                      'сезона','сезонов',
                      'сезонов','сезонов',
                      'сезонов','сезонов']
    series_endings = ['серий','серия',
                      'серии','серии',
                      'серии','серий',
                      'серий','серий',
                      'серий','серий']
    if text_type == 'seasons':
        if 5 <= int(number) <= 15:
            text_ending = 'сезонов'
        else:
            last_digit = int(str(number)[-1])
            text_ending = season_endings[last_digit]
    if text_type == "series":
        if 5 <= int(number) <= 15:
            text_ending = 'серий'
        else:
            last_digit = int(str(number)[-1])
            text_ending = series_endings[last_digit]
    return text_ending


def get_list(freshness = 10_000) -> list:
    """ Получаем из библиотек список элементов с заданной свежестью.
    По умолчанию свежесть равна 10 000 дням, то есть выводятся все элементы.
    Пустые библиотеки не выводятся """
    results = {}
    freshness = freshness*24*60*60    
    for lib in lib_items:       
        items = []        
        for item in lib_items[lib]:
            if time.time() - freshness <= int(item['date_added']):
                if not 'episodes' in item.keys():
                    item_desc = f"{item['title']} ({item['year']}) ⭐ {item['rating']}"
                else:
                    item_desc = f"{item['title']} ({item['year']}) [{item['episodes']}] ⭐ {item['rating']}"
                items.append(item_desc)
        if items:
            results[lib] = items
    return results


def search_by_string(message) -> list:
    """ Получаем из библиотек список элементов с совпадениями по поисковой фразе. Приводим строки
    к нижнему регистру, меняем 'е' на 'ё'. Если найден только один элемент, выводим полное описание"""
    results = {}
    image = None
    caption = None
    search_string = message.casefold()
    search_string = search_string.replace('ё', 'е').replace('.', '').replace(':', '')
    search_string = search_string.replace(',', '').replace('(','').replace(')','').replace('-',' ')
    for lib in lib_items:
        items = []
        for item in lib_items[lib]:
            searchable_title = f"{item['title']} {item['year']}".casefold()
            searchable_title = searchable_title.replace('ё', 'е').replace('.', '')
            searchable_title = searchable_title.replace(':', '').replace(',', '').replace('-',' ')
            if search_string in searchable_title:
                if not 'episodes' in item.keys():
                    item_desc = f"{item['title']} ({item['year']})  ⭐ {item['rating']}::{item['summary']}" \
                                f"::{item['thumb']}"
                else:
                    item_desc = f"{item['title']} ({item['year']}) [{item['episodes']}] ⭐ {item['rating']}::" \
                                f"{item['summary']}::{item['thumb']}"
                items.append(item_desc)
        if items:
            results[lib] = items
    if results:
        if len(results) == 1 and len(list(results.values())[0]) == 1:
            item = str(list(results.values())[0][0])
            desc = item.split('::')
            caption = f"🍿 {desc[0]}\n{desc[1]}"
            thumbnail = f"{desc[2]}"
            urllib.request.urlretrieve(thumbnail, f"{TEMP_DIR}/result.jpg")
            image = FSInputFile(f'{TEMP_DIR}/result.jpg')
            results = 'single_item'
    return results, image, caption


def get_random_item() -> (FSInputFile, str):
    """ Выводим полное описание для случайного элемента """    
    items = []
    for lib in lib_items:
        for item in lib_items[lib]:
            if not 'episodes' in item.keys():
                item_desc = f"{item['title']} ({item['year']})::{item['summary']}" \
                            f"::{item['thumb']}"
            else:
                item_desc = f"{item['title']} ({item['year']}) [{item['episodes']}]::" \
                            f"{item['summary']}::{item['thumb']}"
            items.append(item_desc)
    desc = random.choice(items).split('::')
    caption = f"🍿 {desc[0]}\n{desc[1]}"
    thumbnail = f"{desc[2]}"
    urllib.request.urlretrieve(thumbnail, f"{TEMP_DIR}/result.jpg")
    image = FSInputFile(f'{TEMP_DIR}/result.jpg')
    return image, caption


def compose_message(results, rows) -> list:
    """ Из результатов поиска по библиотеке формируем сообщение, разбивая его на части
    (по количеству строк = rows) из-за ограничения на длину отправляемого сообщения """
    message_parts = []
    for lib in results:
        lines = []
        lines.append(f"{lib} ({len(results[lib])})")
        # Нумеруем результаты
        for number, item in enumerate(results[lib], 1):
            # вырезаем лишнюю информацию
            desc_parts = item.split('::')
            desc = f"{desc_parts[0]}"
            lines.append(f"{number}. {desc}")
        # Разбиваем на части по row строк
        for i in range(0, len(lines), rows):
            message_parts.append(lines[i:i+rows])
    strings_list = []
    # Формируем готовый к отправке список из блоков текста
    for part in message_parts:
        strings_list.append('\n'.join(part))
    return strings_list

## БОТ

# Проверяем токен бота
try:
    token = os.environ["PLEX_BOT_TOKEN"]
except KeyError:
    print('ERROR: Задайте токен бота (eхport PLEX_BOT_TOKEN=XXXXXXXXXXXXXXXXXXXXXXX)')
    sys.exit(1)


# Проверяем наличие white-листа
try:
    white_list = os.environ["PLEX_BOT_ALLOWED_USERS"].split(',')
    print(f'INFO: Белый лист доступа задан: {white_list}')
except KeyError:
    white_list = False
    print('INFO: Белый лист доступа не задан. Бот доступен всем пользователям')

def user_not_allowed(message):
    """ Проверяем пользователя по вайт-листу, если он задан"""
    if white_list:
        return bool(str(message.from_user.id) not in white_list)
    return False


# проверяем адреса библиотек
asyncio.run(load_and_parse())


# бот и диспетчер
bot = Bot(token)
dp = Dispatcher()


async def main() -> None:
    """ Инициализация бота и запуск диспетчера """
    print(f'INFO: SimPlexBot запущен с токеном {token}')    
    await dp.start_polling(bot)


@dp.message(user_not_allowed)
async def reply_to_not_allowed_user(message: Message) -> None:
    """ Пользователь не в вайт-листе """
    print(f"ERROR: Отклонен запрос от пользователя {message.from_user.full_name}" \
          f" (ID:{message.from_user.id}) - пользователь не включен в белый лист")
    await message.answer('Доступ запрещен. Попросите добавить вас в белый лист')
    return


@dp.message(Command('start'))
async def send_welcome(message: Message) -> None:
    """ Обработка команды /start """
    await message.answer(f"Привет, {message.from_user.full_name}!" \
                         f" Введи текст для поиска или выбери команду в меню")


@dp.message(Command('new'))
async def list_new(message: Message) -> None:
    """ Вывод новых элементов по команде /new"""
    await load_and_parse()
    results = get_list(FRESH_DAYS)
    message_parts = compose_message(results, 100)
    for part in message_parts:
        await message.answer(part)


@dp.message(Command('list'))
async def list_all(message: Message) -> None:
    """ Вывод всех элементов по команде /list """
    await load_and_parse()
    results = get_list()
    message_parts = compose_message(results, 50)
    for part in message_parts:
        await message.answer(part)


@dp.message(Command('random'))
async def random_info(message: Message) -> None:
    await load_and_parse()
    """ Вывод подробной информации по случайному элементу """
    thumbnail, caption = get_random_item()
    await message.answer_photo(photo = thumbnail, caption = caption)


@dp.message(F.text)
async def search_text(message: Message) -> None:
    """ Поиск по любой текстовой фразе """
    await load_and_parse()
    results, thumbnail, caption = search_by_string(message.text)
    if results:
        if results != 'single_item':
            message_parts = compose_message(results, 50)
            for part in message_parts:
                await message.answer(part)
        else:
            await message.answer_photo(photo = thumbnail, caption = caption)
    else:
        await message.answer(f" По запросу «{message.text}» ничего не найдено")
    return


if __name__ == "__main__":
    asyncio.run(main())
