import backend.auth as auth


def test_save_and_load_classlink_link(monkeypatch):
    store = {}
    monkeypatch.setattr("backend.storage.save",
                        lambda key, data, scope: store.__setitem__((key, scope), data))
    monkeypatch.setattr("backend.storage.list_keys",
                        lambda prefix, scope: [k for (k, s) in store if k.startswith(prefix)])
    monkeypatch.setattr("backend.storage.load",
                        lambda key, scope: store.get((key, scope)))

    auth.save_classlink_link("classlink:2284:abc", "uuid-1")
    links = auth.load_classlink_links()
    assert links.get("classlink:2284:abc") == "uuid-1"


def test_storage_maps_classlink_link_prefix(tmp_path, monkeypatch):
    """File backend must route classlink_link: keys to a real path."""
    from backend.storage import _key_to_filepath
    path = _key_to_filepath("classlink_link:classlink:2284:abc", teacher_id="some-teacher")
    assert path is not None
    assert "classlink_links" in path
