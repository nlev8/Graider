"""Tests for standards resolution, grade extraction, and grade matching."""
import pytest


@pytest.fixture(autouse=True)
def reset_standards_cache():
    """Reset the module-level standards map cache between tests."""
    import backend.routes.planner_routes as pr
    pr._standards_map_cache = None
    yield
    pr._standards_map_cache = None


class TestExtractGradeFromCode:
    def test_fl_best_math(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('MA.6.AR.1.1') == '6'

    def test_fl_best_science(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('SC.7.E.6.1') == '7'

    def test_fl_best_k12(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('WL.K12.NH.1.1') == 'K12'

    def test_fl_best_912(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('MA.912.AR.1.1') == '912'

    def test_ccss_math(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('CCSS.MATH.CONTENT.6.EE.A.1') == '6'

    def test_ccss_math_8(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('CCSS.MATH.CONTENT.8.G.B.7') == '8'

    def test_ccss_ela(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('CCSS.ELA-LITERACY.RL.6.1') == '6'

    def test_ccss_ela_band(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('CCSS.ELA-LITERACY.RL.9-10.1') == '9-10'

    def test_ngss_middle_school(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('MS-PS1-1') == 'MS'

    def test_ngss_high_school(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('HS-LS1-1') == 'HS'

    def test_c3_social_studies(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('D2.His.1.6-8') == '6-8'

    def test_c3_high_school(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('D2.Civ.1.9-12') == '9-12'

    def test_tx_teks(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('MATH.6.2.A') == '6'

    def test_va_sol(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('MATH.6.1') == '6'

    def test_empty_code(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('') is None

    def test_none_code(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code(None) is None


class TestGradeMatches:
    def test_exact_match(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('6', '6') is True

    def test_no_match(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('6', '7') is False

    def test_k12_matches_all(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('K12', '6') is True
        assert _grade_matches('K12', '12') is True

    def test_ngss_ms_matches_6_7_8(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('MS', '6') is True
        assert _grade_matches('MS', '7') is True
        assert _grade_matches('MS', '8') is True
        assert _grade_matches('MS', '9') is False

    def test_ngss_hs_matches_9_10_11_12(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('HS', '9') is True
        assert _grade_matches('HS', '12') is True
        assert _grade_matches('HS', '8') is False

    def test_grade_band_6_8(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('6-8', '6') is True
        assert _grade_matches('6-8', '8') is True
        assert _grade_matches('6-8', '9') is False

    def test_grade_band_9_10(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('9-10', '9') is True
        assert _grade_matches('9-10', '10') is True
        assert _grade_matches('9-10', '11') is False

    def test_912_band(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('912', '9') is True
        assert _grade_matches('912', '12') is True
        assert _grade_matches('912', '8') is False

    def test_none_grade(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches(None, '6') is False


class TestLoadStandards:
    def test_fl_math_returns_dict(self):
        from backend.routes.planner_routes import load_standards
        result = load_standards('FL', 'Math', '6')
        assert isinstance(result, dict)
        assert 'standards' in result
        assert 'fallback_used' in result
        assert result['fallback_used'] is False

    def test_fl_math_has_standards(self):
        from backend.routes.planner_routes import load_standards
        result = load_standards('FL', 'Math', '6')
        assert len(result['standards']) > 0

    def test_unknown_state_returns_empty(self):
        from backend.routes.planner_routes import load_standards
        result = load_standards('ZZ', 'Math', '6')
        assert isinstance(result, dict)
        assert len(result['standards']) == 0

    def test_no_framework_for_french(self):
        from backend.routes.planner_routes import load_standards
        # FL uses 'fl' framework; French has null fallback in subject_fallbacks
        # and no fl/french.json exists, so no_framework should be True
        result = load_standards('FL', 'French')
        assert result.get('no_framework') is True

    def test_fl_legacy_still_works(self):
        from backend.routes.planner_routes import load_standards
        result = load_standards('FL', 'Civics', '7')
        assert isinstance(result, dict)
        # Should find via standards/fl/civics.json
        assert len(result['standards']) > 0
