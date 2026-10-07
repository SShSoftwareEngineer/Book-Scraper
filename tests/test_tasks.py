"""
Unit tests for Celery background tasks and database persistence workflows.
This module contains test cases for validating task execution, Redis cache interaction,
batching mechanics, and PostgreSQL database persistence in the tasks module.
"""

import json
from types import SimpleNamespace

import tasks
from config import const, db_settings, redis_settings, logging_settings, flower_settings, selectors


def make_book(title='Book', url='https://example.test/book'):
    """
    Helper function to create a sample book dictionary for testing.

    Args:
        title (str, optional): The title of the book. Defaults to 'Book'.
        url (str, optional): The URL of the book. Defaults to 'https://example.test/book'.
    Returns:
        dict: A dictionary containing book attributes formatted like scraped data.
    """
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
    """ Mock Redis cache interface for simulating key-value storage in unit tests. """

    def __init__(self, values=None, keys=None):
        """
        Initialize FakeCache with predefined keys and values.

        Args:
            values (dict, optional): Mapping of cache keys to serialized JSON strings.
            keys (list, optional): List of cache keys available for scanning.
        """
        self.values = values or {}
        self.keys = keys or []
        self.deleted = ()

    def get(self, key):
        """
        Retrieve a value by key from the mock cache.

        Args:
            key (str): The cache key to look up.
        Returns:
            str | None: The cached value if found, otherwise None.
        """
        return self.values.get(key)

    def delete(self, *keys):
        """
        Record deleted cache keys.

        Args:
            *keys: Variable length list of cache keys to delete.
        """
        self.deleted = keys

    def scan_iter(self, match=None, count=None):
        """
        Iterate over mock cache keys.

        Args:
            match (str, optional): Key pattern matching parameter (ignored in mock).
            count (int, optional): Batch size parameter for scanning (ignored in mock).
        Returns:
            Iterator: An iterator over the configured cache keys.
        """
        return iter(self.keys)


class FakeConnection:
    """ Mock database connection object for tracking transaction states. """

    def __init__(self):
        """ Initialize FakeConnection tracking flags. """
        self.committed = False
        self.rolled_back = False

    def commit(self):
        """ Mark the transaction as committed. """
        self.committed = True

    def rollback(self):
        """ Mark the transaction as rolled back. """
        self.rolled_back = True


def test_collect_and_save_returns_empty_list_when_cache_is_empty(monkeypatch):
    """ Test that `collect_and_save` returns an empty list when no keys exist in cache. """
    monkeypatch.setattr(tasks, 'cache', FakeCache(keys=[]))

    assert tasks.collect_and_save.run() == []


def test_collect_and_save_splits_task_ids_into_configured_batches(monkeypatch):
    """ Test that `collect_and_save` splits task IDs into batches based on configuration. """
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
    """ Test that `bulk_save_to_db` processes valid book items, commits transaction, and cleans cache. """
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
    """ Test that `bulk_save_to_db` skips malformed JSON records without failing the batch. """
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
    """ Test that `bulk_save_to_db` triggers rollback and preserves cache upon database error. """
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
