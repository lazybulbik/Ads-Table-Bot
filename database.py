import sqlite3


def register(data, message):
    insert_data = [(message.from_user.id, message.from_user.username, data[0], data[1],
                    str(data[2]) + ', ' + str(data[3]), data[4], '', '', '')]

    with sqlite3.connect('database/database.db') as db:
        cursor = db.cursor()

        query = ''' INSERT INTO users(id, username, name, number, location, radius, favourites, categories, ads) VALUES(?, ?, ?, ?, ?, ?, ? , ?, ?) '''

        cursor.executemany(query, insert_data)
        db.commit()


def update_data(data: dict(), id=None, table=None):
    '''
    обновление данных в бд

    data - словарь в формате <колонна>:<значение> (можно несколько)
    id - обновление произойдет только у определенного пользователя, если None - у всех
    table - таблица, в которой произойдет обновление данных
    '''

    with sqlite3.connect('database/database.db') as db:
        cursor = db.cursor()

        if id != None:
            for key in data:
                update_data = (data[key], id)

                query = f'UPDATE {table} SET {key} = ? where id = ?'
                cursor.execute(query, update_data)

        else:
            for key in data:
                update_data = (data[key],)

                query = f'UPDATE {table} SET {key} = ?'
                cursor.execute(query, update_data)

        db.commit()


def get_data(id=None, table=None):
    '''
    получает данные из бд

    user_id - поиск осуществится по айди юзера, если None возращаеются все данные
    table - поиск произойдет в указаной таблице
    '''

    with sqlite3.connect('database/database.db') as db:
        cursor = db.cursor()

        if id != None:
            select_query = f'SELECT * from {table} where id = ?'
            cursor.execute(select_query, (id,))

        if id == None:
            select_query = f'SELECT * from {table}'
            cursor.execute(select_query)

        data = cursor.fetchall()

        return data


def new_add(data, message):
    user = get_data(message.from_user.id, 'users')[0]

    photo1 = None
    photo2 = None
    photo3 = None
    photo4 = None
    photo5 = None
    photo6 = None

    if len(data['photos']) >= 1:
        photo1 = data['photos'][0]
    if len(data['photos']) >= 2:
        photo2 = data['photos'][1]
    if len(data['photos']) >= 3:
        photo3 = data['photos'][2]
    if len(data['photos']) >= 4:
        photo4 = data['photos'][3]
    if len(data['photos']) >= 5:
        photo5 = data['photos'][4]
    if len(data['photos']) >= 6:
        photo6 = data['photos'][5]

    insert_data = [(message.message_id, data['title'], data['text'], data['price'], photo1, photo2, photo3, photo4, photo5, photo6, data['category'], user[4], user[0])]

    with sqlite3.connect('database/database.db') as db:
        cursor = db.cursor()

        query = ''' INSERT INTO ads(id, title, text, price ,photo1, photo2, photo3, photo4, photo5, photo6, category, location, owner) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) '''

        cursor.executemany(query, insert_data)
        db.commit()

    l = user[8].split()
    l.append(str(message.message_id))

    update_data({'ads': ' '.join(l)}, message.from_user.id, 'users')


def delete(id):
    print(id)
    ad = get_data(id, 'ads')[0]
    owner = ad[12]
    print(owner)

    owners_ads = get_data(owner, 'users')[0][8].split()
    print(owners_ads)
    owners_ads.remove(id)
    update_data({'ads': ' '.join(owners_ads)}, owner, 'users')

    with sqlite3.connect('database/database.db') as db:
        cursor = db.cursor()

        query = f"DELETE from ads where id = {id}"
        cursor.execute(query)
        db.commit()
