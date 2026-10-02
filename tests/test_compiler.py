from app.compiler import compile_assertions
from app.spec_loader import load_spec


def test_spec_has_real_attributes():
    attributes = load_spec()
    assert len(attributes) >= 80
    ids = {a.attribute_id for a in attributes}
    assert len(ids) == len(attributes), "attribute_id must be unique"


def test_compiles_140_plus_assertions():
    attributes = load_spec()
    assertions = compile_assertions(attributes)
    assert len(assertions) >= 140


def test_every_attribute_gets_datatype_and_maxlen():
    attributes = load_spec()
    assertions = compile_assertions(attributes)
    by_attr = {}
    for a in assertions:
        by_attr.setdefault(a.attribute_id, set()).add(a.assertion_type)
    for attr in attributes:
        types = by_attr[attr.attribute_id]
        assert "datatype" in types
        assert "max_length" in types
        if attr.format:
            assert "format" in types
        if attr.enumeration:
            assert "enumeration" in types


def test_compiler_is_deterministic():
    attributes = load_spec()
    first = compile_assertions(attributes)
    second = compile_assertions(attributes)
    assert [a.sql for a in first] == [a.sql for a in second]
