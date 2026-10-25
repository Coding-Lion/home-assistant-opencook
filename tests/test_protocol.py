"""Verify interoperability against upstream's shared Kotlin/Python vectors."""

import itertools

import pytest

from custom_components.opencook.protocol import (
    ClockDriftError,
    Hlc,
    HlcClock,
    apply_all,
    merkle_build,
    merkle_diff,
    merkle_from_dict,
    merkle_to_dict,
)


def test_shared_clock_vectors(vectors):
    for case in vectors["pack"]:
        clock = Hlc(case["millis"], case["counter"], case["node"])
        assert clock.pack() == case["packed"]
        assert Hlc.parse(clock.pack()) == clock
    for case in vectors["order"]:
        comparison = (case["a"] > case["b"]) - (case["a"] < case["b"])
        assert comparison == case["cmp"]


def test_shared_merkle_vectors(vectors):
    for case in vectors["merkle"]["build"]:
        trie = merkle_build(case["timestamps"])
        assert trie.hash == case["rootHash"]
        assert merkle_diff(trie, merkle_from_dict(merkle_to_dict(trie))) is None
    for case in vectors["merkle"]["diff"]:
        assert (
            merkle_diff(merkle_build(case["a"]), merkle_build(case["b"])) == case["expectedMillis"]
        )


def test_shared_merge_vectors_in_every_order(vectors):
    for case in vectors["merge"]:
        for messages in itertools.permutations(case["messages"]):
            store = {}
            apply_all(store, messages)
            assert {"|".join(key): value[0] for key, value in store.items()} == case["expected"]


def test_clock_survives_clock_rollback_and_future_phone():
    clock = HlcClock("ha")
    first = clock.send(1000)
    assert clock.send(900).pack() > first.pack()
    clock.recv(Hlc(5000, 42, "phone"), 1000)
    assert clock.send(1000).pack() > Hlc(5000, 42, "phone").pack()
    with pytest.raises(ClockDriftError):
        HlcClock("ha", Hlc(5000, 65535, "ha")).send(1000)
