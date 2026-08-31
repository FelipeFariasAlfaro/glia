import numpy as np
import pytest

from glia.binding import bind, cosine_similarity, random_vector, unbind
from glia.encoder import encode_text
from glia.plasticity import co_activate, decay_all, reinforce
from glia.resonance import resolve_query, resonate, resonate_multihop
from glia.substrate import GlyphMeta, Substrate


def test_text_encoding_is_deterministic_normalized_and_semantic():
    authentication = encode_text("user authentication login")
    same = encode_text("user authentication login")
    synonym = encode_text("auth signin")
    unrelated = encode_text("database migration schema")

    np.testing.assert_allclose(authentication, same)
    assert np.linalg.norm(authentication) == pytest.approx(1.0)
    assert cosine_similarity(authentication, synonym) > 0.4
    assert cosine_similarity(authentication, synonym) > cosine_similarity(authentication, unrelated)


def test_binding_is_dissimilar_and_can_be_approximately_unbound():
    source = random_vector(seed=11)
    target = random_vector(seed=22)
    relationship = bind(source, target)
    recovered = unbind(relationship, source)

    assert abs(cosine_similarity(relationship, source)) < 0.2
    assert cosine_similarity(recovered, target) > 0.5


def test_store_glyph_replaces_and_moves_weighted_contribution():
    substrate = Substrate()
    original = random_vector(seed=1)
    replacement = random_vector(seed=2)

    glyph = substrate.store_glyph("auth", original, region_id="source")
    substrate.set_glyph_magnitude(glyph, 1.5)
    moved = substrate.store_glyph("auth", replacement, region_id="target")

    np.testing.assert_allclose(substrate.regions["source"].vector, np.zeros(substrate.dimension), atol=1e-12)
    np.testing.assert_allclose(substrate.regions["target"].vector, replacement * 1.5, atol=1e-12)
    assert substrate.regions["source"].glyph_count == 0
    assert substrate.regions["target"].glyph_count == 1
    assert moved.region_id == "target"


def test_store_rejects_vectors_with_wrong_dimension():
    substrate = Substrate(dimension=16)

    with pytest.raises(ValueError, match="Expected vector"):
        substrate.store_glyph("invalid", np.zeros(8))


def test_reinforcement_and_decay_keep_region_superposition_consistent():
    substrate = Substrate()
    vector = random_vector(seed=7)
    glyph = substrate.store_glyph("session", vector)
    initial_activation = glyph.activation_count

    reinforce(glyph, amount=0.5, substrate=substrate)

    assert glyph.magnitude == pytest.approx(1.5)
    assert glyph.activation_count == initial_activation + 1
    np.testing.assert_allclose(substrate.regions["default"].vector, vector * 1.5, atol=1e-12)

    forgotten = decay_all(
        [glyph],
        rate=3.0,
        substrate=substrate,
        now=glyph.last_activated + 3600,
    )

    assert forgotten == 1
    assert glyph.magnitude == 0.0
    np.testing.assert_allclose(substrate.regions["default"].vector, np.zeros(substrate.dimension), atol=1e-12)


def test_resonance_filters_forgotten_glyphs_and_orders_scores():
    stimulus = random_vector(seed=100)
    close = GlyphMeta(id="close", vector=stimulus.copy(), magnitude=1.0)
    weaker = GlyphMeta(id="weaker", vector=stimulus.copy(), magnitude=0.5)
    forgotten = GlyphMeta(id="forgotten", vector=stimulus.copy(), magnitude=0.0)

    results = resonate(stimulus, [weaker, forgotten, close])

    assert [glyph.id for glyph, _ in results] == ["close", "weaker"]
    assert results[0][1] > results[1][1]


def test_multihop_unbinding_discovers_encoded_association():
    substrate = Substrate()
    source_vector = random_vector(seed=31)
    target_vector = random_vector(seed=47)
    source = substrate.store_glyph("source", source_vector)
    target = substrate.store_glyph("target", target_vector)
    substrate.store_relationship(
        bind(source_vector, target_vector),
        relationship_id="test:source-target",
    )

    results = resonate_multihop(
        source_vector,
        [source, target],
        substrate=substrate,
        hops=2,
    )

    assert "source" in [glyph.id for glyph, _ in results]
    assert "target" in [glyph.id for glyph, _ in results]


def test_coactivation_is_identifiable_reversible_and_bounded():
    substrate = Substrate()
    first = substrate.store_glyph("first", random_vector(seed=81))
    second = substrate.store_glyph("second", random_vector(seed=82))

    for _ in range(20):
        relationship = co_activate(
            substrate,
            first,
            second,
            strength=0.1,
            max_norm=0.25,
        )

    assert relationship.id.startswith("plasticity:")
    assert relationship.source == "plasticity:recall"
    assert len(substrate.relationships) == 1
    assert np.linalg.norm(relationship.vector) <= 0.25 + 1e-12
    expected = first.vector + second.vector + relationship.vector
    np.testing.assert_allclose(
        substrate.regions["default"].vector,
        expected,
        atol=1e-12,
    )


def test_explicit_exploration_surfaces_novel_holographic_association():
    substrate = Substrate()
    query = "source concept"
    source_vector = encode_text(query)
    target_vector = next(
        candidate
        for seed in range(907, 2000)
        if cosine_similarity(source_vector, candidate := random_vector(seed=seed)) < 0.0
    )

    substrate.store_glyph(
        "source",
        source_vector,
        source="source.py",
    )
    substrate.store_glyph(
        "direct distractor",
        source_vector,
        source="distractor.py",
    )
    substrate.store_glyph(
        "associated target",
        target_vector,
        source="target.py",
    )
    substrate.store_relationship(
        bind(source_vector, target_vector),
        relationship_id="test:source-target",
        source="test",
    )

    stable = resolve_query(query, substrate, top_k=2, explore=False)
    explored = resolve_query(query, substrate, top_k=2, explore=True)

    assert "associated target" not in [glyph.id for glyph, _ in stable]
    assert "associated target" in [glyph.id for glyph, _ in explored]


def test_resonance_snapshot_is_reused_read_only_and_invalidated_by_mutations():
    substrate = Substrate()
    first = substrate.store_glyph(
        "first", random_vector(seed=501), source="source-a"
    )
    substrate.store_glyph("second", random_vector(seed=502), source="source-b")

    initial = substrate.resonance_snapshot()
    assert substrate.resonance_snapshot() is initial
    assert initial.vectors.flags.writeable is False
    assert initial.scales.flags.writeable is False
    with pytest.raises(ValueError):
        initial.vectors[0, 0] = 0.0

    substrate.set_glyph_magnitude(first, 1.2)
    after_magnitude = substrate.resonance_snapshot()
    assert after_magnitude is not initial
    assert substrate.resonance_snapshot() is after_magnitude

    substrate.store_glyph("third", random_vector(seed=503), source="source-c")
    after_store = substrate.resonance_snapshot()
    assert after_store is not after_magnitude
    assert {glyph.id for glyph in after_store.glyphs} == {"first", "second", "third"}

    substrate.remove_source("source-c")
    after_remove = substrate.resonance_snapshot()
    assert after_remove is not after_store
    assert {glyph.id for glyph in after_remove.glyphs} == {"first", "second"}


def test_managed_glyph_metadata_requires_substrate_mutation_apis():
    substrate = Substrate()
    glyph = substrate.store_glyph("managed", random_vector(seed=611))
    before = substrate.resonance_snapshot()

    with pytest.raises(AttributeError, match="Substrate mutation APIs"):
        glyph.magnitude = 0.0
    with pytest.raises(AttributeError, match="Substrate mutation APIs"):
        glyph.vector = random_vector(seed=612)
    with pytest.raises(ValueError):
        glyph.vector.setflags(write=True)
    with pytest.raises(ValueError):
        glyph.vector[0] = 1.0
    region = substrate.regions["default"]
    with pytest.raises(AttributeError, match="Substrate mutation APIs"):
        region.vector = np.zeros(substrate.dimension)
    with pytest.raises(ValueError):
        region.vector.setflags(write=True)

    substrate.set_glyph_magnitude(glyph, 0.0)
    after_magnitude = substrate.resonance_snapshot()
    assert after_magnitude is not before
    assert after_magnitude.glyphs == ()


def test_magnitude_rejects_metadata_not_owned_by_substrate():
    substrate = Substrate()
    stored = substrate.store_glyph("canonical", random_vector(seed=621))
    impostor = GlyphMeta(
        id=stored.id,
        vector=random_vector(seed=622),
        magnitude=stored.magnitude,
    )
    before = substrate.regions["default"].vector.copy()

    with pytest.raises(KeyError, match="does not belong"):
        substrate.set_glyph_magnitude(impostor, 2.0)

    assert stored.magnitude == pytest.approx(1.0)
    np.testing.assert_allclose(substrate.regions["default"].vector, before)
