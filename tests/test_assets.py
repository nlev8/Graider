"""Tests for the Assets / resource storage feature."""
import pytest
import os


class TestResourceStorage:
    def test_resource_key_maps_to_filepath(self):
        from backend.storage import _key_to_filepath
        path = _key_to_filepath('resource:abc-123')
        assert path is not None
        assert 'resources' in path
        assert 'abc-123.json' in path

    def test_resource_save_and_load_local(self):
        from backend.storage import save, load, delete
        test_data = {"title": "Test Assessment", "type": "assessment"}
        assert save('resource:test-asset-1', test_data, 'local-dev')
        loaded = load('resource:test-asset-1', 'local-dev')
        assert loaded is not None
        assert loaded['title'] == "Test Assessment"
        delete('resource:test-asset-1', 'local-dev')

    def test_resource_list_keys(self):
        from backend.storage import save, list_keys, delete
        save('resource:list-test-1', {"title": "A"}, 'local-dev')
        save('resource:list-test-2', {"title": "B"}, 'local-dev')
        keys = list_keys('resource:', 'local-dev')
        assert 'resource:list-test-1' in keys
        assert 'resource:list-test-2' in keys
        delete('resource:list-test-1', 'local-dev')
        delete('resource:list-test-2', 'local-dev')

    def test_resource_delete(self):
        from backend.storage import save, load, delete
        save('resource:del-test', {"title": "Delete Me"}, 'local-dev')
        assert delete('resource:del-test', 'local-dev')
        assert load('resource:del-test', 'local-dev') is None
