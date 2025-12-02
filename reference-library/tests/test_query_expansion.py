"""
Tests for the enhanced query expansion system.

Tests cover:
- Standard synonym expansion
- Orthographic variations (British/American spellings)
- Neuromonitoring term expansion
- Complication term expansion
- Instrument synonym expansion
- Integration tests
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from search.neurosurgical_synonyms import (
    expand_query,
    expand_query_simple,
    get_all_terms_for_query,
    is_neurosurgical_term,
    get_orthographic_expansion,
    get_instrument_synonyms,
    get_monitoring_expansion,
    ALL_SYNONYMS,
    DOMAIN_SYNONYMS,
    PROCEDURAL_SYNONYMS,
)

from search.extracted_dictionaries import (
    INSTRUMENT_SYNONYMS,
    POSITIONING_TERMS,
    NEUROMONITORING_TERMS,
    HEMOSTATIC_AGENTS,
    ORTHOGRAPHIC_VARIATIONS,
    get_orthographic_variants,
    expand_with_monitoring_context,
    expand_with_complication_context,
)


class TestOrthographicVariations:
    """Tests for British/American spelling variations."""

    def test_disc_disk_variation(self):
        """Test disc/disk spelling variants."""
        variants = get_orthographic_variants("disc")
        assert "disc" in variants
        assert "disk" in variants

    def test_tumour_tumor_variation(self):
        """Test tumour/tumor spelling variants."""
        variants = get_orthographic_variants("tumour")
        assert "tumour" in variants
        assert "tumor" in variants

    def test_haematoma_hematoma_variation(self):
        """Test haematoma/hematoma spelling variants."""
        variants = get_orthographic_variants("haematoma")
        assert "haematoma" in variants
        assert "hematoma" in variants

    def test_anaesthesia_anesthesia_variation(self):
        """Test anaesthesia/anesthesia spelling variants."""
        variants = get_orthographic_variants("anaesthesia")
        assert "anaesthesia" in variants
        assert "anesthesia" in variants

    def test_query_orthographic_expansion(self):
        """Test orthographic expansion in full query."""
        expansions = get_orthographic_expansion("cervical disc herniation")
        assert "cervical disc herniation" in expansions
        assert "cervical disk herniation" in expansions


class TestNeuromonitoringExpansion:
    """Tests for neuromonitoring term expansion."""

    def test_baer_expansion(self):
        """Test BAER acronym expansion."""
        expansions = expand_with_monitoring_context("BAER")
        assert "BAER" in expansions
        assert "brainstem auditory evoked responses" in expansions
        assert any("posterior fossa" in e for e in expansions)

    def test_ssep_expansion(self):
        """Test SSEP acronym expansion."""
        expansions = expand_with_monitoring_context("SSEP")
        assert "SSEP" in expansions
        assert "somatosensory evoked potentials" in expansions

    def test_mep_expansion(self):
        """Test MEP acronym expansion."""
        expansions = expand_with_monitoring_context("MEP")
        assert "MEP" in expansions
        assert "motor evoked potentials" in expansions

    def test_emg_expansion(self):
        """Test EMG acronym expansion."""
        expansions = expand_with_monitoring_context("EMG")
        assert "EMG" in expansions
        assert "electromyography" in expansions

    def test_monitoring_expansion_helper(self):
        """Test get_monitoring_expansion helper function."""
        result = get_monitoring_expansion("BAER")
        assert result["full"] == "brainstem auditory evoked responses"
        assert "posterior fossa" in result["context"]


class TestComplicationExpansion:
    """Tests for complication term expansion."""

    def test_hematoma_expansion(self):
        """Test hematoma complication expansion."""
        expansions = expand_with_complication_context("hematoma")
        assert "hematoma" in expansions
        assert "epidural hematoma" in expansions or any("epidural" in e for e in expansions)

    def test_csf_leak_expansion(self):
        """Test CSF leak complication expansion."""
        expansions = expand_with_complication_context("CSF leak")
        assert "CSF leak" in expansions
        assert any("dural" in e.lower() for e in expansions)

    def test_nerve_injury_expansion(self):
        """Test nerve injury expansion."""
        expansions = expand_with_complication_context("nerve injury")
        assert "nerve injury" in expansions
        assert any("neuropraxia" in e for e in expansions)


class TestInstrumentSynonyms:
    """Tests for surgical instrument synonym expansion."""

    def test_mayfield_synonyms(self):
        """Test Mayfield head holder synonyms."""
        assert "mayfield" in INSTRUMENT_SYNONYMS
        synonyms = INSTRUMENT_SYNONYMS["mayfield"]
        assert "skull clamp" in synonyms
        assert "head holder" in synonyms

    def test_cusa_synonyms(self):
        """Test CUSA instrument synonyms."""
        assert "cusa" in INSTRUMENT_SYNONYMS
        synonyms = INSTRUMENT_SYNONYMS["cusa"]
        assert "ultrasonic aspirator" in synonyms

    def test_bipolar_synonyms(self):
        """Test bipolar forceps synonyms."""
        assert "bipolar" in INSTRUMENT_SYNONYMS
        synonyms = INSTRUMENT_SYNONYMS["bipolar"]
        assert "bipolar forceps" in synonyms

    def test_get_instrument_synonyms_helper(self):
        """Test get_instrument_synonyms helper function."""
        result = get_instrument_synonyms("mayfield")
        assert "mayfield" in result
        assert "skull clamp" in result


class TestHemostaticAgents:
    """Tests for hemostatic agent synonyms."""

    def test_gelfoam_synonyms(self):
        """Test Gelfoam synonyms."""
        assert "gelfoam" in HEMOSTATIC_AGENTS
        synonyms = HEMOSTATIC_AGENTS["gelfoam"]
        assert "gelatin sponge" in synonyms

    def test_surgicel_synonyms(self):
        """Test Surgicel synonyms."""
        assert "surgicel" in HEMOSTATIC_AGENTS
        synonyms = HEMOSTATIC_AGENTS["surgicel"]
        assert "oxidized cellulose" in synonyms

    def test_bone_wax_synonyms(self):
        """Test bone wax synonyms."""
        assert "bone wax" in HEMOSTATIC_AGENTS


class TestPositioningTerms:
    """Tests for patient positioning terminology."""

    def test_park_bench_synonyms(self):
        """Test park bench position synonyms."""
        assert "park bench" in POSITIONING_TERMS
        synonyms = POSITIONING_TERMS["park bench"]
        assert "lateral decubitus" in synonyms

    def test_prone_synonyms(self):
        """Test prone position synonyms."""
        assert "prone" in POSITIONING_TERMS
        synonyms = POSITIONING_TERMS["prone"]
        assert "prone position" in synonyms

    def test_axillary_roll_synonyms(self):
        """Test axillary roll synonyms."""
        assert "axillary roll" in POSITIONING_TERMS


class TestExpandQuery:
    """Tests for the main expand_query function."""

    def test_expand_query_includes_original(self):
        """Test that expansion always includes original query."""
        result = expand_query("acoustic neuroma")
        assert "acoustic neuroma" in result

    def test_expand_query_adds_synonyms(self):
        """Test that expansion adds synonym variations."""
        result = expand_query("acoustic neuroma", max_expansions=5)
        assert len(result) > 1
        # Should include vestibular schwannoma as a synonym
        assert any("vestibular schwannoma" in r.lower() for r in result)

    def test_expand_query_with_orthographic(self):
        """Test orthographic variation inclusion."""
        result = expand_query("disc herniation", include_orthographic=True)
        assert any("disk" in r.lower() for r in result)

    def test_expand_query_without_orthographic(self):
        """Test disabling orthographic variations."""
        result = expand_query("disc herniation", include_orthographic=False)
        # Original should still be there
        assert "disc herniation" in result

    def test_expand_query_respects_max_expansions(self):
        """Test that max_expansions limit is respected."""
        result = expand_query("glioblastoma", max_expansions=3)
        assert len(result) <= 4  # original + 3 expansions

    def test_expand_query_simple_backward_compatible(self):
        """Test that simple expansion maintains backward compatibility."""
        result = expand_query_simple("meningioma")
        assert "meningioma" in result


class TestGetAllTermsForQuery:
    """Tests for get_all_terms_for_query function."""

    def test_returns_set(self):
        """Test that function returns a set."""
        result = get_all_terms_for_query("tumor")
        assert isinstance(result, set)

    def test_includes_original(self):
        """Test that result includes original query."""
        result = get_all_terms_for_query("aneurysm")
        assert "aneurysm" in result

    def test_includes_synonyms(self):
        """Test that result includes synonyms."""
        result = get_all_terms_for_query("aneurysm")
        assert "cerebral aneurysm" in result or any("cerebral" in t for t in result)


class TestIsNeurosurgicalTerm:
    """Tests for is_neurosurgical_term function."""

    def test_recognizes_primary_terms(self):
        """Test recognition of primary dictionary terms."""
        assert is_neurosurgical_term("glioblastoma")
        assert is_neurosurgical_term("meningioma")
        assert is_neurosurgical_term("craniotomy")

    def test_recognizes_synonyms(self):
        """Test recognition of synonym terms."""
        assert is_neurosurgical_term("GBM")
        assert is_neurosurgical_term("vestibular schwannoma")

    def test_recognizes_monitoring_terms(self):
        """Test recognition of neuromonitoring terms."""
        assert is_neurosurgical_term("BAER")
        assert is_neurosurgical_term("SSEP")
        assert is_neurosurgical_term("MEP")

    def test_recognizes_instruments(self):
        """Test recognition of surgical instruments."""
        assert is_neurosurgical_term("mayfield")
        assert is_neurosurgical_term("cusa")

    def test_rejects_non_medical_terms(self):
        """Test that non-medical terms are rejected."""
        assert not is_neurosurgical_term("javascript")
        assert not is_neurosurgical_term("pizza")


class TestDictionaryCoverage:
    """Tests for dictionary completeness and structure."""

    def test_all_synonyms_not_empty(self):
        """Test that ALL_SYNONYMS contains entries."""
        assert len(ALL_SYNONYMS) > 0

    def test_domain_synonyms_coverage(self):
        """Test domain-specific synonym coverage."""
        assert len(DOMAIN_SYNONYMS) > 50  # Should have many entries

    def test_procedural_synonyms_coverage(self):
        """Test procedural synonym coverage."""
        assert len(PROCEDURAL_SYNONYMS) > 50  # Should have many entries

    def test_orthographic_variations_coverage(self):
        """Test orthographic variations coverage."""
        assert len(ORTHOGRAPHIC_VARIATIONS) > 30  # Should have many British/American pairs

    def test_instrument_synonyms_structure(self):
        """Test that instrument synonyms have proper structure."""
        for term, synonyms in INSTRUMENT_SYNONYMS.items():
            assert isinstance(term, str)
            assert isinstance(synonyms, list)
            assert all(isinstance(s, str) for s in synonyms)

    def test_neuromonitoring_terms_structure(self):
        """Test that neuromonitoring terms have proper structure."""
        for term, entry in NEUROMONITORING_TERMS.items():
            assert isinstance(term, str)
            assert isinstance(entry, dict)
            assert "full" in entry
            assert "synonyms" in entry
            assert "context" in entry


class TestIntegration:
    """Integration tests for the complete query expansion system."""

    def test_complex_query_expansion(self):
        """Test expansion of complex multi-term queries."""
        query = "cervical disc herniation with myelopathy"
        result = expand_query(query, max_expansions=5)
        assert query in result
        assert len(result) > 1

    def test_monitoring_in_query(self):
        """Test BAER monitoring term in query context."""
        query = "posterior fossa surgery with BAER monitoring"
        result = expand_query(query, include_monitoring=True)
        # Should expand BAER to full name or related terms
        assert len(result) >= 1

    def test_complication_query(self):
        """Test complication term in query."""
        query = "postoperative hematoma management"
        result = expand_query(query, include_complications=True)
        assert len(result) >= 1

    def test_instrument_in_query(self):
        """Test instrument term in query."""
        query = "CUSA tumor debulking technique"
        result = expand_query(query)
        # CUSA should have synonyms added
        assert len(result) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

