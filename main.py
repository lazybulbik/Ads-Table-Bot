import os
import random

from aiogram import Bot, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher
from aiogram.types import ParseMode, InputFile
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from geopy import Nominatim
from geopy.distance import geodesic
from phonenumbers import parse

import ads_processing
import buffers
import config
import database
import menu

bot = Bot(config.TELEGRAM_TOKEN, parse_mode=ParseMode.MARKDOWN)
dp = Dispatcher(bot, storage=MemoryStorage())


@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message):
    """
    обработка команды /start
    если юзера нет в бд, регистрируем его
    """

    state = dp.current_state(user=message.from_user.id)  # получаем состояние пользователя

    users_id = [user[0] for user in database.get_data(table='users')]  # получаем айди зарегистрированых людей

    if message.from_user.id not in users_id:  # проверяем зарегестрирован ли пользователь
        # если пользователь не зрегистрирован
        await message.answer('Привет! Я вижу Вы используете бота вперые. Зарегестрируйтесь для работы с ботом. \
                             \n\nКак Вас зовут?', reply_markup=types.ReplyKeyboardRemove())

        await state.set_state('register:name')  # меняем состояние для регистрации

    else:
        # если пользователь зарегестирован
        await bot.send_photo(chat_id=message.from_user.id,
                             photo=InputFile('media/start.jpg'),
                             caption='Добро пожаловать в бота по поиску ближайших объявлений!',
                             reply_markup=menu.main_menu)

        await state.reset_state()  # сбрасываем состояние, для избежания ошибок


@dp.message_handler(content_types=[types.ContentType.TEXT, types.ContentType.CONTACT, types.ContentType.LOCATION],
                    state=['register:name', 'register:number', 'register:location', 'register:radius'])
async def register(message: types.Message):
    """
    функция регистрации пользователей, собираемые данные: имя, телефон, геолокация, радиус поиска
    """

    state = dp.current_state(user=message.from_user.id)  # получение состояния пользователя
    curent_state = await state.get_state()

    step = curent_state.split(':')[1]  # узнаем на каком шаге регистрации пользователь

    if step == 'name':
        # получение имени пользователя
        if message.content_type == 'text':
            buffers.register_buf[message.from_user.id] = list()
            buffers.register_buf[message.from_user.id].append(message.text.title())  # складываем имя в временный буфер

            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(types.KeyboardButton(text="Отправить номер телефона 📱",
                                              request_contact=True))  # создаем клавиатуру для запроса телефона

            await message.answer(
                'Запомнил, теперь отправьте номер телефона в формате, что бы пользователи могли связаться с вами. \n\nФормат номера: +x xxx xxx xx-xx \n\nИли просто нажмите на кнопку ниже.',
                reply_markup=keyboard)
            await state.set_state('register:number')  # меняем состояние на получение телефона
        else:
            await message.answer('Отправь свое имя.')

    elif step == 'number':
        # получение номера телефона
        if message.content_type == 'contact':  # если юзер отправил контакт
            number = message.contact.phone_number  # если юзер отправил текст
        elif message.content_type == 'text':
            try:
                x = parse(message.text)  # проверяем номер ли это
            except:
                await message.answer('Отправьте номер телефона в формате +x xxx xxx xx-xx, или нажмите на кнопку ниже')
                return

            number = message.text  # получем номер
        else:
            await message.answer('Отправьте свой номер телефона!')
            return

        buffers.register_buf[message.from_user.id].append(number)  # складываем номер в временный буфер

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.KeyboardButton(text="Отправить геолокацию 🛰", request_location=True))

        await message.answer('Отлично! Отправьте свою геолокацию, для более лучшего подбора объявлений.',
                             reply_markup=keyboard)
        await state.set_state('register:location')  # меняем состояние на получение геолокации

    elif step == 'location':
        # получение геолокации
        if message.content_type == "location":
            buffers.register_buf[message.from_user.id].append(
                message.location.latitude)  # помещаем широту в временный буфер
            buffers.register_buf[message.from_user.id].append(
                message.location.longitude)  # помещаем долготу в временный буфер

            await message.answer(
                'Осталось совсем чуть-чуть. Отправьте радиус, в котором искать объявления. (целое число, в метрах)',
                reply_markup=types.ReplyKeyboardRemove())
            await state.set_state('register:radius')  # меняем состояние на получение радиуса

        else:
            await message.answer('Отправьте свою геопозицию.')

    elif step == 'radius':
        # получение радиуса
        try:
            radius = int(message.text)  # проверяем отправил ли пользователь целое число
        except:
            await message.answer('Отправьте целое число!')
            return

        buffers.register_buf[message.from_user.id].append(radius)  # помещяем в временный буфер радиус

        await message.answer('Спасибо за регистрацию! \nТеперь Вы можете пользоваться всеми возможностями бота',
                             reply_markup=types.ReplyKeyboardRemove())

        await bot.send_photo(chat_id=message.from_user.id,
                             photo=InputFile('media/start.jpg'),
                             caption='Добро пожаловать в бота по поиску ближайших объявлений!',
                             reply_markup=menu.main_menu)

        await state.reset_state()  # сбрасываем состояние

        database.register(buffers.register_buf[message.from_user.id],
                          message)  # добавляем данные из временного буфера в бд
        del buffers.register_buf[message.from_user.id]  # удаляем данные с временного буфера


@dp.message_handler(content_types=types.ContentType.TEXT)
async def main_menu(message: types.Message):
    """
    обработка комманд главного меню
    """
    state = dp.current_state(user=message.from_user.id)

    if message.text == menu.profile_button.text:  # обработка кнопки "Профиль"
        user = database.get_data(id=message.from_user.id, table='users')[0]
        nominatim = Nominatim(user_agent='user')

        name = user[2]
        number = user[3]
        location = str(nominatim.reverse(user[4])).split(', ')
        location = location[0] + ', ' + location[1] + ', ' + location[2] + ', ' + location[-1]
        radius = user[5]

        text = f"Ваш профиль:" \
               f"\nИмя: *{name}*" \
               f"\nНомер телефона: *{number}*" \
               f"\nГеолокация: *{location}*" \
               f"\nРадиус поиска: *{radius} м*"

        await message.answer(text, reply_markup=menu.profile_menu)
        await state.set_state('profile')

    elif message.text == menu.place_add_button.text:  # обработка кнопки "Разместить объявление"
        await message.answer('Отлично! Размещаем объявление. Выберите категорию.', reply_markup=menu.categories_menu)
        await state.set_state('place_add:category')  # меняем состояние на запрос категории

    elif message.text == menu.find_ads_button.text:
        await message.answer('Выберите категории для поиска', reply_markup=menu.categories_menu)
        await state.set_state('find_ads:category')

    elif message.text == menu.favourites_button.text:
        ads = database.get_data(message.from_user.id, 'users')[0][6].split()

        if len(ads) != 0:
            keyboard = InlineKeyboardMarkup()
            buttons = []

            for ad in ads:
                try:
                    ad_data = database.get_data(ad, 'ads')[0]
                    buttons.append(InlineKeyboardButton(ad_data[1], callback_data=f'favourites:view:{ad_data[0]}'))
                except:
                    ads.remove(ad)
                    database.update_data({'favourites': ' '.join(ads)}, message.from_user.id, 'users')

            keyboard.add(*buttons)

            await message.answer('Ваши избранные объявления.', reply_markup=keyboard)
        else:
            await message.answer('У Вас нет избранных объявлений.')

    elif message.text == menu.subscribes_button.text:
        await message.answer('Категории для подписки', reply_markup=menu.get_subscribe_buttons(message.from_user.id))


@dp.message_handler(content_types=types.ContentType.TEXT, state='find_ads:category')
async def find_ads(message: types.Message):
    state = dp.current_state(user=message.from_user.id)

    if message.text == menu.back_button.text:
        await message.answer('Вы в главном меню.', reply_markup=menu.main_menu)
        try:
            del buffers.find_add_buf[message.from_user.id]
        except:
            pass
        await state.reset_state()

        return

    if message.text in menu.names:
        ads_id = ads_processing.find_ads(message.from_user.id, message.text)

        if len(ads_id) == 0:
            await message.answer('Не удалось найти подходящие объявления.' +
                                 '\n\nПопробуйте изменить радиус поиска, или выбрать другую категорию')
            return

        await message.answer('Поиск.', reply_markup=menu.main_menu)
        await state.reset_state()

        user = database.get_data(message.from_user.id, 'users')[0]
        user_coord = tuple(user[4].split(', '))

        for id in ads_id[:3]:
            ad = database.get_data(id, 'ads')[0]
            ad_coord = tuple(ad[11].split(', '))

            photo = ad[4]
            title = ad[1]
            text = ad[2]
            price = ad[3]
            distance = geodesic(ad_coord, user_coord).m
            salesname = database.get_data(ad[12], 'users')[0][2]
            number = database.get_data(ad[12], 'users')[0][3]
            photos_count = 6 - list(ad[4:10]).count(None)

            write = InlineKeyboardButton('Связаться', callback_data=f'find_ads:write:{str(number)}')

            ad_keyboard = InlineKeyboardMarkup()
            ad_keyboard.add(write)

            favourites = user[6].split()
            if ad[0] not in favourites:
                favourites_btn = InlineKeyboardButton('В избранное', callback_data=f'find_ads:favourites:{ad[0]}')
                ad_keyboard.add(favourites_btn)

            if photos_count > 1:
                more = InlineKeyboardButton('Показать все фото', callback_data=f'find_ads:more_photo:{ad[0]}')
                ad_keyboard.add(more)

            caption = f'*{title}* ' \
                      f'\n\n{text} ' \
                      f'\n\nПродавец: *{salesname}*' \
                      f'\nЦена: *{price} KRW*' \
                      f'\n\nРасстояние: *{int(distance)} м*'

            if photo != None:
                await bot.send_photo(chat_id=message.from_user.id,
                                     photo=photo,
                                     caption=caption,
                                     reply_markup=ad_keyboard)

            else:
                await message.answer(caption, reply_markup=ad_keyboard)

        if len(ads_id) > 3:
            more = InlineKeyboardButton('Показать', callback_data=f'find_ads:more:{message.text}:3')
            keyboard = InlineKeyboardMarkup().add(more)
            await message.answer('Найдено еще несколько объвлений. Показать?', reply_markup=keyboard)


    else:
        await message.answer('Выберите один из вариантов ниже!')


@dp.message_handler(content_types=[types.ContentType.TEXT, types.ContentType.CONTACT, types.ContentType.LOCATION],
                    state=['profile', 'profile:radius', 'profile:contact'])
async def profile(message: types.Message):
    """
    Обработка кнопок в разделе профиль
    """
    state = dp.current_state(user=message.from_user.id)
    curent_state = await state.get_state()

    if curent_state == 'profile:radius':  # обновление радиуса
        if message.text == menu.back_button.text:  # обработка кнопки назад
            await state.set_state('profile')

        else:
            try:
                radius = int(message.text)  # проверяем отправил ли пользователь целое число
            except:
                await message.answer('Отправьте целое число!')
                return

            database.update_data({'radius': radius}, id=message.from_user.id, table='users')  # добавляем радиус в бд
            await state.set_state('profile')

    elif curent_state == 'profile:contact':  # обновление контакта
        if message.text == 'Назад':  # обработка кнопки назад
            await state.set_state('profile')

        else:
            if message.content_type == 'contact':  # если юзер отправил контакт
                number = message.contact.phone_number  # если юзер отправил текст
            elif message.content_type == 'text':
                try:
                    x = parse(message.text)  # проверяем номер ли это
                except:
                    await message.answer(
                        'Отправьте номер телефона в формате +x xxx xxx xx-xx, или нажмите на кнопку ниже')
                    return

                number = message.text  # получем номер
            else:
                await message.answer('Отправьте свой номер телефона!')
                return

            database.update_data({'number': number}, id=message.from_user.id, table='users')  # обновляем номе в бд

            await state.set_state('profile')

    else:
        if message.content_type == 'location':  # обновление геолокации в бд
            database.update_data({'location': str(message.location.latitude) + ', ' + str(message.location.longitude)},
                                 id=message.from_user.id,
                                 table='users')  # вносим новую геолокацию в бд в бд

        elif message.text == menu.change_number_button.text:  # обработка кнопки "Обновить контакт"
            back_button = KeyboardButton('Назад')
            number_button = KeyboardButton('Отправить номер телефона 📱', request_contact=True)
            back_menu = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1).add(number_button, back_button)

            await message.answer('Отправьте номер телефона \n\n*Формат номера: +x xxx xxx xx-xx*',
                                 reply_markup=back_menu)

            await state.set_state('profile:contact')  # перенаправляем на получение контакта
            return

        elif message.text == menu.change_radius_button.text:  # изменение радиуса поиска
            await message.answer('Отправьте радиус, в котором искать объявления. (целое число, в метрах)',
                                 reply_markup=menu.back_menu)

            await state.set_state('profile:radius')  # перенаправляем на получение радиуса
            return

        elif message.text == menu.my_ads_button.text:
            ads = database.get_data(message.from_user.id, 'users')[0][8].split()

            if len(ads) != 0:
                keyboard = InlineKeyboardMarkup()
                buttons = []

                for ad in ads:
                    ad_data = database.get_data(ad, 'ads')[0]
                    buttons.append(InlineKeyboardButton(ad_data[1], callback_data=f'my_ads:{ad_data[0]}'))

                keyboard.add(*buttons)

                await message.answer('Ваши объявления.', reply_markup=keyboard)

            else:
                await message.answer('У Вас нет объявлений.')
            return

        elif message.text == menu.back_main_menu_button.text:  # в гланое меню
            await message.answer('Вы в главном меню.', reply_markup=menu.main_menu)
            await state.reset_state()
            return

    user = database.get_data(id=message.from_user.id, table='users')[0]  # получаем юзера
    nominatim = Nominatim(user_agent='user')

    name = user[2]  # получаем имя
    number = user[3]  # получаем номер
    location = str(nominatim.reverse(user[4])).split(', ')
    location = location[0] + ', ' + location[1] + ', ' + location[2] + ', ' + location[-1]  # получаем локацию
    radius = user[5]  # получаем радиус

    text = f"Ваш профиль:" \
           f"\nИмя: *{name}*" \
           f"\nНомер телефона: *{number}*" \
           f"\nГеолокация: *{location}*" \
           f"\nРадиус поиска: *{radius} м*"

    await message.answer(text, reply_markup=menu.profile_menu)


@dp.message_handler(content_types=[types.ContentType.TEXT, types.ContentType.PHOTO],
                    state=['place_add:category', 'place_add:title', 'place_add:text', 'place_add:photo',
                           'place_add:price'])
async def place_add(message: types.Message):
    state = dp.current_state(user=message.from_user.id)
    step = await state.get_state()
    step = step.split(':')[1]

    if message.content_type == 'text':
        if step == 'category':
            if message.text == menu.back_button.text:
                await message.answer('Вы в главном меню.', reply_markup=menu.main_menu)
                try:
                    del buffers.place_add_buf[message.chat.id]
                except:
                    pass
                await state.reset_state()
                return

            if message.text in menu.names:
                buffers.place_add_buf[message.from_user.id] = dict()
                buffers.place_add_buf[message.from_user.id]['category'] = message.text
                await message.answer('Прекрасно! теперь введите название объявления (не более 50 символов)',
                                     reply_markup=menu.back_menu)
                await state.set_state('place_add:title')

            else:
                await message.answer('Выберите один из пунктов ниже!')

        elif step == 'title':
            if message.text == menu.back_button.text:
                await message.answer('Назад! Выберите категорию.',
                                     reply_markup=menu.categories_menu)
                await state.set_state('place_add:category')
                return

            if len(message.text) <= 50:
                buffers.place_add_buf[message.from_user.id]['title'] = message.text
                await message.answer('Теперь введите описание объявления (не более 900 символов)',
                                     reply_markup=menu.back_menu)
                await state.set_state('place_add:text')


            else:
                await message.answer('Максимальная длина названия 50 символов!')


        elif step == 'text':
            if message.text == menu.back_button.text:
                await message.answer('Назад! Введите название объявления')
                await state.set_state('place_add:title')
                return

            if len(message.text) <= 900:
                buffers.place_add_buf[message.from_user.id]['text'] = message.text

                keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
                next = KeyboardButton('Продолжить без фото')
                keyboard.add(next, menu.back_button)

                await message.answer('Теперь пришлите фотографии для объявления (максимум 6 фото)',
                                     reply_markup=keyboard)
                buffers.place_add_buf[message.chat.id]['photos'] = list()
                buffers.place_add_buf[message.chat.id]['pre_photos'] = list()

                await state.set_state('place_add:photo')


            else:
                await message.answer('Максимальная длина описания 900 символов!')

        elif step == 'price':
            if message.text == menu.back_button.text:
                keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
                next = KeyboardButton('Продолжить без фото')
                keyboard.add(next, menu.back_button)

                await message.answer('Назад! Пришлите фотографии для объявления (максимум 6 фото)',
                                     reply_markup=keyboard)
                buffers.place_add_buf[message.from_user.id]['photos'].clear()
                buffers.place_add_buf[message.from_user.id]['pre_photos'].clear()
                await state.set_state('place_add:photo')
                return

            try:
                price = int(message.text)
            except:
                await message.answer('Введите число!')
                return

            buffers.place_add_buf[message.from_user.id]['price'] = price

            database.new_add(buffers.place_add_buf[message.from_user.id], message)
            del buffers.place_add_buf[message.from_user.id]

            await message.answer('Ваше объявление опубликовано!', reply_markup=menu.main_menu)
            await state.reset_state()

            ad = database.get_data(message.message_id, 'ads')[0]
            ad_category = ad[10]
            ad_coord = tuple(ad[11].split(', '))
            photo = ad[4]
            title = ad[1]
            text = ad[2]
            price = ad[3]
            salesname = database.get_data(ad[12], 'users')[0][2]
            number = database.get_data(ad[12], 'users')[0][3]
            photos_count = 6 - list(ad[4:10]).count(None)

            for user in database.get_data(table='users'):
                subs_category = user[7].split(', ')
                user_coord = tuple(user[4].split(', '))

                distance = geodesic(ad_coord, user_coord).m

                if ad_category in subs_category and distance <= int(user[5]) and str(ad[12]) != str(user[0]):
                    user_coord = tuple(user[4].split(', '))

                    write = InlineKeyboardButton('Связаться', callback_data=f'find_ads:write:{str(number)}')
                    favourites_btn = InlineKeyboardButton('В избранное', callback_data=f'find_ads:favourites:{ad[0]}')

                    ad_keyboard = InlineKeyboardMarkup()
                    ad_keyboard.add(write, favourites_btn)

                    if photos_count > 1:
                        more = InlineKeyboardButton('Показать все фото', callback_data=f'find_ads:more_photo:{ad[0]}')
                        ad_keyboard.add(more)

                    distance = geodesic(ad_coord, user_coord).m

                    caption = f'*Опубликовано новое объявление в разделе {ad_category}!*' \
                              f'\n\n*{title}* ' \
                              f'\n\n{text} ' \
                              f'\n\nПродавец: *{salesname}*' \
                              f'\nЦена: *{price} KRW*' \
                              f'\n\nРасстояние: *{int(distance)} м*'

                    if photo != None:
                        await bot.send_photo(chat_id=user[0],
                                             photo=photo,
                                             caption=caption,
                                             reply_markup=ad_keyboard)

                    else:
                        await bot.send_message(user[0], caption, reply_markup=ad_keyboard)

    if step == 'photo':
        if message.content_type == 'text':
            if message.text == 'Продолжить' or message.text == 'Продолжить без фото':
                count = len(buffers.place_add_buf[message.from_user.id]['pre_photos'])

                for photo in buffers.place_add_buf[message.from_user.id]['pre_photos']:
                    if type(photo) is bytes:
                        continue

                    await photo.download('media/' + str(message.from_user.id) + photo['file_unique_id'] + '.jpg')

                    with open('media/' + str(message.from_user.id) + photo['file_unique_id'] + '.jpg', 'rb') as file:
                        buffers.place_add_buf[message.from_user.id]['photos'].append(file.read())
                        # buffers.place_add_buf[message.from_user.id]['pre_photos'].remove(photo)

                    os.remove('media/' + str(message.from_user.id) + photo['file_unique_id'] + '.jpg')

                await message.answer(f'Фотографий в Вашем объявлени: {count}. Теперь укажите цену (KRW).',
                                     reply_markup=menu.back_menu)

                await state.set_state('place_add:price')


            elif message.text == 'Очистить фото':
                buffers.place_add_buf[message.from_user.id]['pre_photos'].clear()

                keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
                next = KeyboardButton('Продолжить без фото')
                keyboard.add(next, menu.back_button)

                await message.answer('Все фото в объявлении очищены.', reply_markup=keyboard)

            elif message.text == menu.back_button.text:
                await message.answer('Назад! Введите описание объявления (не более 900 символов)',
                                     reply_markup=menu.back_menu)
                await state.set_state('place_add:text')
                return

        elif message.content_type == 'photo':

            if len(buffers.place_add_buf[message.from_user.id]['pre_photos']) < 6:
                buffers.place_add_buf[message.from_user.id]['pre_photos'].append(message.photo[-1])

                next = KeyboardButton('Продолжить')
                clear = KeyboardButton('Очистить фото')
                keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
                keyboard.add(next, clear, menu.back_button)

                await message.reply('Фото добавлено', reply_markup=keyboard)

            else:
                await message.reply('Максимальное количество фото: 6!')

    print(buffers.place_add_buf)


@dp.message_handler(content_types=types.ContentType.TEXT, state='*')
async def edit_ads(message: types.Message):
    state = dp.current_state(user=message.from_user.id)
    curent_state = await state.get_state()
    curent_state = curent_state.split(':')
    step = curent_state[0]
    id = curent_state[1]

    if step == 'edit_price':
        try:
            price = int(message.text)
        except:
            await message.answer('Введите целое число!')
            return

        database.update_data({'price': price}, id, 'ads')
        await message.answer('Цена изменена.', reply_markup=menu.profile_menu)
        await state.set_state('profile')

    if step == 'edit_title':
        if len(message.text) <= 50:
            database.update_data({'title': message.text}, id, 'ads')
            await message.answer('Название изменено.', reply_markup=menu.profile_menu)
            await state.set_state('profile')
        else:
            await message.answer('Максимальная длина 50 символов!')

    if step == 'edit_text':
        if len(message.text) <= 900:
            database.update_data({'text': message.text}, id, 'ads')
            await message.answer('Описание изменено.', reply_markup=menu.profile_menu)
            await state.set_state('profile')
        else:
            await message.answer('Максимальная длина 900 символов!')


@dp.callback_query_handler(state="*")
async def inlines_button(callback_query: types.CallbackQuery):
    state = dp.current_state(user=callback_query.from_user.id)

    if 'my_ads' in callback_query.data:
        if callback_query.data.split(':')[1] == 'back':
            ads = database.get_data(callback_query.from_user.id, 'users')[0][8].split()

            keyboard = InlineKeyboardMarkup()
            buttons = []

            for ad in ads:
                ad_data = database.get_data(ad, 'ads')[0]
                buttons.append(InlineKeyboardButton(ad_data[1], callback_data=f'my_ads:{ad_data[0]}'))

            keyboard.add(*buttons)

            await bot.delete_message(message_id=callback_query.message.message_id,
                                     chat_id=callback_query.from_user.id)
            await bot.send_message(callback_query.from_user.id, 'Ваши объявления', reply_markup=keyboard)

        elif callback_query.data.split(':')[1] == 'edit_price':
            await bot.delete_message(message_id=callback_query.message.message_id,
                                     chat_id=callback_query.from_user.id)

            await bot.send_message(callback_query.from_user.id,
                                   'Введите новую цену (KRW)')

            data = callback_query.data.split(':')

            await state.set_state(f'{data[1]}:{data[2]}')

        elif callback_query.data.split(':')[1] == 'edit_title':
            await bot.delete_message(message_id=callback_query.message.message_id,
                                     chat_id=callback_query.from_user.id)

            await bot.send_message(callback_query.from_user.id,
                                   'Введите новое название (не более 50 символов)')

            data = callback_query.data.split(':')

            await state.set_state(f'{data[1]}:{data[2]}')

        elif callback_query.data.split(':')[1] == 'edit_text':
            await bot.delete_message(message_id=callback_query.message.message_id,
                                     chat_id=callback_query.from_user.id)

            await bot.send_message(callback_query.from_user.id,
                                   'Введите новое описание (не более 900 символов)')

            data = callback_query.data.split(':')

            await state.set_state(f'{data[1]}:{data[2]}')

        elif callback_query.data.split(':')[1] == 'delete':
            data = callback_query.data.split(':')

            yes = InlineKeyboardButton('Да', callback_data=f'my_ads:delete_sure:{data[2]}')
            no = InlineKeyboardButton('Нет', callback_data=f'my_ads:{data[2]}')
            keyboard = InlineKeyboardMarkup().add(yes).add(no)

            await bot.edit_message_reply_markup(chat_id=callback_query.from_user.id,
                                                message_id=callback_query.message.message_id,
                                                reply_markup=keyboard)

        elif callback_query.data.split(':')[1] == 'delete_sure':
            data = callback_query.data.split(':')
            database.delete(data[2])

            await bot.delete_message(message_id=callback_query.message.message_id,
                                     chat_id=callback_query.from_user.id)

            await bot.send_message(callback_query.from_user.id, 'Объявление удалено')

        else:
            ad = database.get_data(callback_query.data.split(':')[1], 'ads')[0]
            title = ad[1]
            text = ad[2]
            price = ad[3]

            keyboard = InlineKeyboardMarkup(row_width=1)
            edit_price = InlineKeyboardButton('Редактировать цену', callback_data=f'my_ads:edit_price:{ad[0]}')
            edit_title = InlineKeyboardButton('Редактировать название', callback_data=f'my_ads:edit_title:{ad[0]}')
            edit_text = InlineKeyboardButton('Редактировать описание', callback_data=f'my_ads:edit_text:{ad[0]}')
            delete = InlineKeyboardButton('Удалить', callback_data=f'my_ads:delete:{ad[0]}')
            back = InlineKeyboardButton('Назад', callback_data='my_ads:back')
            keyboard.add(edit_price, edit_title, edit_text, delete, back)

            await bot.delete_message(message_id=callback_query.message.message_id,
                                     chat_id=callback_query.from_user.id)

            if ad[4] == None:
                await bot.send_message(callback_query.from_user.id, f'*{title}* \n\n{text} \n\n{price}',
                                       reply_markup=keyboard)
            else:
                await bot.send_photo(photo=ad[4],
                                     chat_id=callback_query.from_user.id,
                                     caption=f'*{title}* \n\n{text} \n\n{price} KRW',
                                     reply_markup=keyboard)

    if 'find_ads' in callback_query.data:
        parts = callback_query.data.split(':')
        action = parts[1]

        if action == 'write':
            await bot.answer_callback_query(callback_query.id,
                                            show_alert=True,
                                            text=f'Номер телефона: {parts[2]}')

        if action == 'favourites':
            user = database.get_data(callback_query.from_user.id, 'users')[0]
            try:
                ad = database.get_data(parts[2], 'ads')[0]
            except:
                await callback_query.answer('Объявление было удалено владельцем')
                await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
                return

            l = user[6].split()
            l.append(parts[2])
            database.update_data({'favourites': ' '.join(l)}, callback_query.from_user.id, 'users')

            number = database.get_data(ad[12], 'users')[0][3]

            write = InlineKeyboardButton('Связаться', callback_data=f'find_ads:write:{str(number)}')
            ad_keyboard = InlineKeyboardMarkup()
            ad_keyboard.add(write)

            photos_count = 6 - list(ad[4:10]).count(None)
            if photos_count > 1:
                more = InlineKeyboardButton('Показать все фото', callback_data=f'find_ads:more_photo:{ad[0]}')
                ad_keyboard.add(more)

            await bot.answer_callback_query(callback_query.id,
                                            show_alert=False,
                                            text='Объявление добавлено в избранное')

            await bot.edit_message_reply_markup(chat_id=callback_query.from_user.id,
                                                message_id=callback_query.message.message_id,
                                                reply_markup=ad_keyboard)

        if action == 'more_photo':
            try:
                ad = database.get_data(parts[2], 'ads')[0]
            except:
                await callback_query.answer('Объявление было удалено владельцем')
                await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
                return

            photos = ad[4:10]
            media_group = types.MediaGroup()

            trash = []

            for photo in photos:
                if photo == None:
                    continue

                filename = str(random.randint(1, 999999)) + '.png'

                with open(filename, 'wb') as file:
                    file.write(photo)

                media_group.attach_photo(photo=InputFile(filename))

                trash.append(filename)

            await bot.send_media_group(chat_id=callback_query.from_user.id,
                                       media=media_group,
                                       reply_to_message_id=callback_query.message.message_id)
            for t in trash:
                os.remove(t)

        if action == 'more':
            count = int(parts[3])

            ads_id = ads_processing.find_ads(callback_query.from_user.id, parts[2])

            user = database.get_data(callback_query.from_user.id, 'users')[0]
            user_coord = tuple(user[4].split(', '))

            await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

            for id in ads_id[count:count + 3]:
                ad = database.get_data(id, 'ads')[0]
                ad_coord = tuple(ad[11].split(', '))

                photo = ad[4]
                title = ad[1]
                text = ad[2]
                price = ad[3]
                distance = geodesic(ad_coord, user_coord).m
                salesname = database.get_data(ad[12], 'users')[0][2]
                number = database.get_data(ad[12], 'users')[0][3]
                photos_count = 6 - list(ad[4:10]).count(None)

                write = InlineKeyboardButton('Связаться', callback_data=f'find_ads:write:{str(number)}')

                ad_keyboard = InlineKeyboardMarkup()
                ad_keyboard.add(write)

                favourites = user[6].split()
                if ad[0] not in favourites:
                    favourites_btn = InlineKeyboardButton('В избранное', callback_data=f'find_ads:favourites:{ad[0]}')
                    ad_keyboard.add(favourites_btn)

                if photos_count > 1:
                    more = InlineKeyboardButton('Показать все фото', callback_data=f'find_ads:more_photo:{ad[0]}')
                    ad_keyboard.add(more)

                caption = f'*{title}* ' \
                          f'\n\n{text} ' \
                          f'\n\nПродавец: *{salesname}*' \
                          f'\nЦена: *{price} KRW*' \
                          f'\n\nРасстояние: *{int(distance)} м*'

                if photo != None:
                    await bot.send_photo(chat_id=callback_query.from_user.id,
                                         photo=photo,
                                         caption=caption,
                                         reply_markup=ad_keyboard)

                else:
                    await bot.send_message(callback_query.from_user.id, caption, reply_markup=ad_keyboard)

            if len(ads_id) > count + 3:
                more = InlineKeyboardButton('Показать', callback_data=f'find_ads:more:{parts[2]}:{count + 3}')
                keyboard = InlineKeyboardMarkup().add(more)
                await bot.send_message(callback_query.from_user.id,
                                       'Найдено еще несколько объявлений. Показать?',
                                       reply_markup=keyboard)

    if 'favourites' in callback_query.data:
        parts = callback_query.data.split(':')
        action = parts[1]

        if action == 'back':
            ads = database.get_data(callback_query.from_user.id, 'users')[0][6].split()

            if len(ads) != 0:
                keyboard = InlineKeyboardMarkup()
                buttons = []

                for ad in ads:
                    try:
                        ad_data = database.get_data(ad, 'ads')[0]
                        buttons.append(InlineKeyboardButton(ad_data[1], callback_data=f'favourites:view:{ad_data[0]}'))
                    except:
                        ads.remove(ad)
                        database.update_data({'favourites': ' '.join(ads)}, callback_query.from_user.id, 'users')

                keyboard.add(*buttons)

                await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

                await bot.send_message(callback_query.from_user.id, 'Ваши избранные объявления.', reply_markup=keyboard)
            else:
                await bot.send_message(callback_query.from_user.id, 'У Вас нет избранных объявлений.')

        if action == 'view':
            try:
                ad = database.get_data(parts[2], 'ads')[0]
            except:
                await callback_query.answer('Это объявление было удалено владельцем')

                user = database.get_data(callback_query.from_user.id, 'users')[0]

                l = user[6].split()
                l.remove(parts[2])
                database.update_data({'favourites': ' '.join(l)}, callback_query.from_user.id, 'users')

                ads = database.get_data(callback_query.from_user.id, 'users')[0][6].split()

                if len(ads) != 0:
                    keyboard = InlineKeyboardMarkup()
                    buttons = []

                    for ad in ads:
                        try:
                            ad_data = database.get_data(ad, 'ads')[0]
                            buttons.append(InlineKeyboardButton(ad_data[1], callback_data=f'favourites:view:{ad_data[0]}'))
                        except:
                            ads.remove(ad)
                            database.update_data({'favourites': ' '.join(ads)}, callback_query.from_user.id, 'users')

                    keyboard.add(*buttons)

                    await bot.send_message(callback_query.from_user.id,
                                           'Ваши избранные объявления.',
                                           reply_markup=keyboard)
                else:
                    await bot.send_message(callback_query.from_user.id,
                                                'У Вас нет избранных объявлений.')

                await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
                return

            title = ad[1]
            text = ad[2]
            price = ad[3]
            photo = ad[4]
            salesname = database.get_data(ad[12], 'users')[0][2]
            number = database.get_data(ad[12], 'users')[0][3]
            photos_count = 6 - list(ad[4:10]).count(None)

            keyboard = InlineKeyboardMarkup(row_width=2)
            write = InlineKeyboardButton('Связаться', callback_data=f'find_ads:write:{str(number)}')
            del_favourites = InlineKeyboardButton('Убрать из избранного', callback_data=f'del_favourites:{ad[0]}')
            back = InlineKeyboardButton('Назад', callback_data='favourites:back')
            keyboard.add(write, del_favourites)

            if photos_count > 1:
                more = InlineKeyboardButton('Показать все фото', callback_data=f'find_ads:more_photo:{ad[0]}')
                keyboard.add(more)

            keyboard.add(back)

            caption = f'*{title}* ' \
                      f'\n\n{text} ' \
                      f'\n\nПродавец: *{salesname}*' \
                      f'\nЦена: *{price} KRW*'

            await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

            if photo != None:
                await bot.send_photo(chat_id=callback_query.from_user.id,
                                     photo=photo,
                                     caption=caption,
                                     reply_markup=keyboard)
            else:
                await bot.send_message(callback_query.from_user.id, caption, reply_markup=keyboard)

    if 'del_favourites' in callback_query.data:
        parts = callback_query.data.split(':')

        user_fav = database.get_data(callback_query.from_user.id, 'users')[0][6].split()
        user_fav.remove(parts[1])
        database.update_data({'favourites': ' '.join(user_fav)}, callback_query.from_user.id, 'users')

        ads = database.get_data(callback_query.from_user.id, 'users')[0][6].split()

        if len(ads) != 0:
            keyboard = InlineKeyboardMarkup()
            buttons = []

            for ad in ads:
                try:
                    ad_data = database.get_data(ad, 'ads')[0]
                    buttons.append(InlineKeyboardButton(ad_data[1], callback_data=f'favourites:view:{ad_data[0]}'))
                except:
                    ads.remove(ad)
                    database.update_data({'favourites': ' '.join(ads)}, callback_query.from_user.id, 'users')

            keyboard.add(*buttons)

            await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

            await bot.send_message(callback_query.from_user.id, 'Ваши избранные объявления.', reply_markup=keyboard)
        else:
            await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
            await bot.send_message(callback_query.from_user.id, 'У Вас нет избранных объявлений.')

        await callback_query.answer('Объявление удалено из избранных')

    if 'subscribes' in callback_query.data:
        parts = callback_query.data.split(':')
        action = parts[1]

        user = database.get_data(callback_query.from_user.id, 'users')[0]

        if action == 'set':
            l = user[7].split(', ')
            l.append(parts[2])

            database.update_data({'categories': ', '.join(l)}, callback_query.from_user.id, 'users')

            await bot.edit_message_text(text=callback_query.message.text,
                                        chat_id=callback_query.from_user.id,
                                        message_id=callback_query.message.message_id,
                                        reply_markup=menu.get_subscribe_buttons(callback_query.from_user.id))

            await callback_query.answer(
                f'Вы подписались на категорию {parts[2]}, Вы будете получать уведомления о новых объявлениях')

        if action == 'del':
            l = user[7].split(', ')
            l.remove(parts[2])

            database.update_data({'categories': ', '.join(l)}, callback_query.from_user.id, 'users')

            await bot.edit_message_text(text=callback_query.message.text,
                                        chat_id=callback_query.from_user.id,
                                        message_id=callback_query.message.message_id,
                                        reply_markup=menu.get_subscribe_buttons(callback_query.from_user.id))

            await callback_query.answer(
                f'Вы отписались от категории {parts[2]}, теперь Вы не будете получать уведомления о новых объявлениях')

    await bot.answer_callback_query(callback_query.id)


@dp.message_handler(content_types=types.ContentType.PHOTO)
async def photo(message: types.Message):
    print(message.photo[0].file_id)


executor.start_polling(dp)
