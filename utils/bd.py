import sqlite3
from typing import Union, Dict, List, Tuple

DATA_TYPES = {int: 'INTEGER', str: 'TEXT', bool: 'BOOL', float: 'FLOAT'}


class TypeOptions:
    def __init__(self, type: Union[int, str, bool, float], not_null: bool = False, is_primary: bool = False, autoincrement: bool = False):
        primary = ' PRIMARY KEY' if is_primary else ''
        autoincrement = ' AUTOINCREMENT' if autoincrement else ''
        not_null = ' Not NULL' if not_null else ''
        if type in DATA_TYPES:
            type = DATA_TYPES[type]
        self.str = f'{type}{not_null}{primary}{autoincrement}'

    def __str__(self) -> str:
        return self.str


ID = TypeOptions(int, not_null=True, is_primary=True, autoincrement=True)


class DataBase:
    def __init__(self, path: str):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()

    def __del__(self):
        self.connection.close()

    def commit(self) -> None:
        self.connection.commit()

    def execute(self, query: str) -> sqlite3.Cursor:
        # print(query)
        return self.cursor.execute(query)

    def create_table(self, table: str, columns: Dict[str, Union[int, str, bool, float, TypeOptions]], unique: Union[Tuple[str], List[str], str] = None) -> None:
        for column, type in columns.items():
            if type in DATA_TYPES:
                columns[column] = DATA_TYPES[type]
        columns = ',\n'.join(
            f'{column} {type}' for column, type in columns.items())
        if unique:
            if not isinstance(unique, str):
                unique = ','.join(unique)
            columns += f',\nUNIQUE({unique})'
        self.execute(f'''
            --beginsql
            CREATE TABLE IF NOT EXISTS {table}(
                {columns}
            )
            --endsql
            ''')
        self.commit()

    def drop_table(self, table: str) -> None:
        self.execute(f'''
            --beginsql
            DROP TABLE IF EXISTS {table}
            --endsql
            ''')
        self.commit()

    def insert(self, table: str, data: Dict[str, Union[int, str, bool, float]]) -> None:
        keys = ', '.join(str(i) for i in data.keys())
        values = ', '.join(str(i) for i in data.values())
        self.execute(f'''
            --beginsql
            INSERT OR REPLACE INTO {table} ({keys}) VALUES ({values})
            --endsql
            ''')
        self.commit()

    def select(self, table: str, columns: Union[Tuple[str], List[str], str], optional: str = '', order_by: Union[str, None] = None) -> list:
        if not isinstance(columns, str):
            columns = ', '.join(columns)
        order_by = f' ORDER BY {order_by}' if order_by else ''
        if optional:
            optional = f' {optional}'
        data = self.execute(f'''
            --beginsql
            SELECT {columns} FROM {table}{order_by}{optional}
            --endsql
            ''')
        return [dict(row) for row in data.fetchall()]

    def update(self, table: str, data: Dict[str, Union[int, str, bool, float]], where: str) -> None:
        data = ', '.join(f'{k} = {v}' for k, v in data.items())
        if where.lower().startswith('where'):
            where = where[5:]
        self.execute(f'''
            --beginsql
            UPDATE {table}
            SET {data}
            WHERE {where}
            --endsql
            ''')

    def delete(self, table: str, columns: Union[Tuple[str], List[str], str], where: str = None, order_by: Union[str, None] = None, limit: int = None, offset: int = None) -> list:
        if not isinstance(columns, str):
            columns = ', '.join(columns)
        where = f'WHERE {where}' if where else ''
        order_by = f'ORDER BY {order_by}' if order_by else ''
        limit = f'LIMIT {limit}' if limit else ''
        offset = f'OFFSET {offset}' if offset else ''
        data = self.execute(f'''
            --beginsql
            DELETE FROM {table}
            {where}
            {order_by}
            {limit}
            {offset}
            --endsql
            ''')
        return [dict(row) for row in data.fetchall()]


db = DataBase('instruity.db')
db.drop_table('songs')
db.create_table('saved', {'id': ID,
                          'url': str,
                          'user_id': int,
                          'slot': int}, unique=('user_id', 'slot'))

db.insert('saved', {'slot': 1, 'user_id': 3, 'url': 123})
db.insert('saved', {'slot': 1, 'user_id': 5, 'url': 12345679789})
db.insert('saved', {'slot': 2, 'user_id': 5, 'url': 1})
print(db.select('saved', '*'))
print()

# 1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣🔟
