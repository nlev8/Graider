"""Phase 4.1 PR2 — `get_api_key` and `resolve_keys_for_teacher` must accept
explicit `district_id` kwarg for Celery (no Flask context).

Providers used today: openai, anthropic, gemini (NOT google).
"""
from unittest.mock import patch


def test_get_api_key_accepts_explicit_district_id():
    """Caller passes district_id explicitly → _get_district_id() is NOT called."""
    from backend.api_keys import get_api_key
    with patch('backend.api_keys._load_user_keys', return_value={}):
        with patch('backend.api_keys._load_district_keys', return_value={'openai': 'district-key-123'}) as mock_load:
            with patch('backend.api_keys._get_district_id') as mock_g:
                result = get_api_key('openai', 'test-teacher', district_id='test-district')
    assert result == 'district-key-123'
    mock_load.assert_called_with('test-district')
    mock_g.assert_not_called()  # explicit arg bypasses the flask.g lookup


def test_get_api_key_falls_back_to_flask_g_when_kwarg_missing():
    """Backward compat: existing callers that don't pass district_id still resolve via flask.g."""
    from backend.api_keys import get_api_key
    with patch('backend.api_keys._load_user_keys', return_value={}):
        with patch('backend.api_keys._load_district_keys', return_value={'openai': 'fallback-key'}) as mock_load:
            with patch('backend.api_keys._get_district_id', return_value='flask-g-district') as mock_g:
                result = get_api_key('openai', 'test-teacher')  # no district_id kwarg
    assert result == 'fallback-key'
    mock_load.assert_called_with('flask-g-district')
    mock_g.assert_called_once()


def test_resolve_keys_for_teacher_accepts_explicit_district_id():
    """resolve_keys_for_teacher must pass district_id through to every key resolution."""
    from backend.api_keys import resolve_keys_for_teacher
    with patch('backend.api_keys._load_user_keys', return_value={}):
        with patch('backend.api_keys._load_district_keys', return_value={'openai': 'ok'}) as mock_load:
            with patch('backend.api_keys._get_district_id') as mock_g:
                result = resolve_keys_for_teacher('test-teacher', district_id='explicit-district')
    mock_load.assert_called_with('explicit-district')
    mock_g.assert_not_called()
    assert isinstance(result, dict)
    # Must include at least openai, anthropic, gemini keys (match current shape)
    assert 'openai' in result
    assert 'anthropic' in result
    assert 'gemini' in result


def test_all_five_resolution_layers_preserved_by_bytecode():
    """AST safety rail: new get_api_key must still reference ALL the same
    symbols as before. Catches regression where a layer is silently dropped.
    """
    import ast
    with open('backend/api_keys.py') as f:
        tree = ast.parse(f.read())
    get_api_key_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'get_api_key':
            get_api_key_fn = node
            break
    assert get_api_key_fn is not None, "get_api_key function must exist"
    names_referenced = {n.id for n in ast.walk(get_api_key_fn) if isinstance(n, ast.Name)}
    # All 5 layers must appear somewhere in the function body
    required = {'_thread_keys', '_load_user_keys', '_load_district_keys', '_get_district_id', '_ENV_MAP'}
    missing = required - names_referenced
    assert not missing, f"get_api_key dropped these resolution-layer symbols: {missing}"
