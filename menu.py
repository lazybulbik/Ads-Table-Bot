from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton

import database

# нопки главного меню
place_add_button = KeyboardButton('Разместить объявление')
find_ads_button = KeyboardButton('Поиск объявлений')
profile_button = KeyboardButton('Профиль')
subscribes_button = KeyboardButton('Подписки')
favourites_button = KeyboardButton('Избранное')
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(place_add_button, find_ads_button)
main_menu.add(profile_button)
main_menu.add(subscribes_button, favourites_button)

# кнопка возращения в главное меню
back_main_menu_button = KeyboardButton('Главное меню')
back_main_menu = ReplyKeyboardMarkup(resize_keyboard=True).add(back_main_menu_button)

# кнопка назад
back_button = KeyboardButton('Назад')
back_menu = ReplyKeyboardMarkup(resize_keyboard=True).add(back_button)

# кнопки раздела профиль
my_ads_button = KeyboardButton('Мои объявления')
change_number_button = KeyboardButton('Обновить номер телефона')
change_location_button = KeyboardButton('Обновить геолокацию', request_location=True)
change_radius_button = KeyboardButton('Изменить радиус поиска')
profile_menu = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1).add(my_ads_button,
                                                                          change_number_button,
                                                                          change_location_button,
                                                                          change_radius_button,
                                                                          back_main_menu_button)

# кнопки категории объявления
names = ['Работа', 'Электроника', 'Хозтовары', 'Интерьер', 'Искусство', 'Животные', 'Спорт/Отдых', 'Транспорт',
         'Одежда/Обувь', 'Разное', 'Недвижимость', 'Услуги', 'Детские товары', 'Красота и здоровье']
back_inline_button = InlineKeyboardButton('Назад', callback_data='back')

categories_menu = ReplyKeyboardMarkup(resize_keyboard=True).add(
    *[KeyboardButton(text=name, callback_data=name) for name in names])
categories_menu.add(back_button)


def get_subscribe_buttons(id):
    user = database.get_data(id, 'users')[0]
    subs_categories = user[7].split(', ')

    keyboard = InlineKeyboardMarkup(row_width=1)

    for name in names:
        if name in subs_categories:
            button = InlineKeyboardButton(text=f'{name}: отписаться', callback_data=f'subscribes:del:{name}')
        else:
            button = InlineKeyboardButton(text=f'{name}: подписаться', callback_data=f'subscribes:set:{name}')

        keyboard.add(button)

    return keyboard