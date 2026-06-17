import json
from types import SimpleNamespace

import tasks


def make_book(title='Book', url='https://example.test/book'):
    return {
        'title': title,
        'category': 'Fiction',
        'price': 'GBP 10.00',
        'rating': 'Three',
        'available': 'In stock',
        'image_url': 'https://example.test/image.jpg',
        'description': 'Description',
        'product_info': {'UPC': '123'},
        'url': url,
    }


class FakeCache:
    def __init__(self, values=None, keys=None):
        self.values = values or {}
        self.keys = keys or []
        self.deleted = ()

    def get(self, key):
        return self.values.get(key)

    def delete(self, *keys):
        self.deleted = keys

    def scan_iter(self, match=None, count=None):
        return iter(self.keys)


class FakeConnection:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_collect_and_save_returns_empty_list_when_cache_is_empty(monkeypatch):
    monkeypatch.setattr(tasks, 'cache', FakeCache(keys=[]))

    assert tasks.collect_and_save.run() == []


def test_collect_and_save_splits_task_ids_into_configured_batches(monkeypatch):
    submitted_batches = []

    def fake_delay(batch):
        submitted_batches.append(batch)
        return SimpleNamespace(id=f'batch-{len(submitted_batches)}')

    monkeypatch.setattr(tasks, 'cache', FakeCache(keys=['book:1', 'book:2', 'book:3']))
    monkeypatch.setattr(tasks.const, 'batch_size', 2)
    monkeypatch.setattr(tasks.bulk_save_to_db, 'delay', fake_delay)

    assert tasks.collect_and_save.run() == ['batch-1', 'batch-2']
    assert submitted_batches == [['1', '2'], ['3']]


def test_bulk_save_to_db_writes_valid_books_as_one_batch(monkeypatch):
    fake_cache = FakeCache(values={
        'book:1': json.dumps(make_book(title='First', url='https://example.test/1')),
        'book:2': json.dumps(make_book(title='Second', url='https://example.test/2')),
    })
    fake_connection = FakeConnection()
    executed = {}

    def fake_execute_batch(cursor, sql, rows):
        executed['cursor'] = cursor
        executed['sql'] = sql
        executed['rows'] = rows

    monkeypatch.setattr(tasks, 'cache', fake_cache)
    monkeypatch.setattr(tasks, 'execute_batch', fake_execute_batch)
    monkeypatch.setattr(tasks.bulk_save_to_db, '_db_cursor', object())
    monkeypatch.setattr(tasks.bulk_save_to_db, '_db_connection', fake_connection)

    saved_count = tasks.bulk_save_to_db.run(['1', '2'])

    assert saved_count == 2
    assert len(executed['rows']) == 2
    assert executed['rows'][0][0] == 'First'
    assert executed['rows'][1][0] == 'Second'
    assert fake_connection.committed is True
    assert fake_connection.rolled_back is False
    assert fake_cache.deleted == ('book:1', 'book:2')


def test_bulk_save_to_db_skips_invalid_json(monkeypatch):
    fake_cache = FakeCache(values={
        'book:1': '{not-json',
        'book:2': json.dumps(make_book(title='Valid', url='https://example.test/valid')),
    })
    fake_connection = FakeConnection()
    executed = {}

    def fake_execute_batch(cursor, sql, rows):
        executed['rows'] = rows

    monkeypatch.setattr(tasks, 'cache', fake_cache)
    monkeypatch.setattr(tasks, 'execute_batch', fake_execute_batch)
    monkeypatch.setattr(tasks.bulk_save_to_db, '_db_cursor', object())
    monkeypatch.setattr(tasks.bulk_save_to_db, '_db_connection', fake_connection)

    saved_count = tasks.bulk_save_to_db.run(['1', '2'])

    assert saved_count == 1
    assert len(executed['rows']) == 1
    assert executed['rows'][0][0] == 'Valid'
    assert fake_cache.deleted == ('book:2',)


def test_bulk_save_to_db_rolls_back_and_keeps_cache_on_database_error(monkeypatch):
    fake_cache = FakeCache(values={
        'book:1': json.dumps(make_book()),
    })
    fake_connection = FakeConnection()

    def fake_execute_batch(cursor, sql, rows):
        raise tasks.psycopg2.DatabaseError('boom')

    monkeypatch.setattr(tasks, 'cache', fake_cache)
    monkeypatch.setattr(tasks, 'execute_batch', fake_execute_batch)
    monkeypatch.setattr(tasks.bulk_save_to_db, '_db_cursor', object())
    monkeypatch.setattr(tasks.bulk_save_to_db, '_db_connection', fake_connection)

    saved_count = tasks.bulk_save_to_db.run(['1'])

    assert saved_count == 0
    assert fake_connection.committed is False
    assert fake_connection.rolled_back is True
    assert fake_cache.deleted == ()
