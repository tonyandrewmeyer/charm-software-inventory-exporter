# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing
"""Unit tests for lib/charms/software_inventory_provider/v0/software_inventory.py module."""
from dataclasses import asdict
from unittest.mock import MagicMock, call

import pytest
from charms.software_inventory_exporter.v0.software_inventory import (
    ExporterConfig,
    SoftwareInventoryConsumer,
    SoftwareInventoryProvider,
)


def test_provider_init():
    """Test initialization of a Provider endpoint."""
    relation_name = "my-relation"
    port = "5000"
    address = "10.0.0.10"

    endpoint = SoftwareInventoryProvider(MagicMock(), relation_name, address, port)

    assert endpoint.port == port
    assert endpoint.bound_address == address
    assert endpoint.relation_name == relation_name


def test_provider_on_consumer_joined(mocker):
    """Test that provider endpoint triggers right action when consumer joins."""
    event_mock = MagicMock()
    relation_mock = MagicMock()
    event_mock.relation = relation_mock
    update_relation_mock = mocker.patch.object(SoftwareInventoryProvider, "_update_relation_data")

    endpoint = SoftwareInventoryProvider(MagicMock())
    endpoint._on_consumer_joined(event_mock)

    update_relation_mock.assert_called_once_with(relation_mock)


def test_provider_update_relation_data_explicit_binding(generic_charm_harness):
    """Test 'Provider' updating unit data in relations if explicit exporter address is defined."""
    local_charm = generic_charm_harness.charm
    local_unit = local_charm.unit.name
    exporter_addr = "10.0.0.10"
    model_name = generic_charm_harness.model.name

    with generic_charm_harness.hooks_disabled():
        rel_id = generic_charm_harness.add_relation("software-inventory", "collector")
        generic_charm_harness.add_relation_unit(rel_id, "collector/0")

    relation = generic_charm_harness.model.relations["software-inventory"][0]
    endpoint = SoftwareInventoryProvider(charm=local_charm, bound_address=exporter_addr)

    endpoint._update_relation_data(relation)

    expected_relation_data = ExporterConfig(endpoint.bound_address, endpoint.port, model_name)
    assert asdict(expected_relation_data) == generic_charm_harness.get_relation_data(
        rel_id, local_unit
    )


def test_provider_update_relation_data_implicit_binding(generic_charm_harness, mocker):
    """Test 'Provider' updating unit data in relations if exporter listens on all adrresses.

    This happens when exporter's configuration is '0.0.0.0'. In this case, bind address
    of a relation endpoint should be used instead.
    """
    local_charm = generic_charm_harness.charm
    local_unit = local_charm.unit.name
    model_name = generic_charm_harness.model.name
    binding_address = "192.168.100.1"
    relation_binding = MagicMock()
    relation_binding.network.bind_address = binding_address
    mocker.patch.object(
        generic_charm_harness.charm.model, "get_binding", return_value=relation_binding
    )

    with generic_charm_harness.hooks_disabled():
        rel_id = generic_charm_harness.add_relation("software-inventory", "collector")
        generic_charm_harness.add_relation_unit(rel_id, "collector/0")

    relation = generic_charm_harness.model.relations["software-inventory"][0]
    endpoint = SoftwareInventoryProvider(charm=local_charm)

    endpoint._update_relation_data(relation)

    expected_relation_data = ExporterConfig(binding_address, endpoint.port, model_name)
    assert asdict(expected_relation_data) == generic_charm_harness.get_relation_data(
        rel_id, local_unit
    )


def test_provider_update_relation_data_implicit_binding_fails(generic_charm_harness, mocker):
    """Test 'Provider' updating unit data in relations if exporter listens on all adrresses.

    This happens when exporter's configuration is '0.0.0.0'. In this case, bind address
    of a relation endpoint should be used instead.

    This test scenario test failure of getting relation binding.
    """
    local_charm = generic_charm_harness.charm
    mocker.patch.object(generic_charm_harness.charm.model, "get_binding", return_value=None)

    with generic_charm_harness.hooks_disabled():
        rel_id = generic_charm_harness.add_relation("software-inventory", "collector")
        generic_charm_harness.add_relation_unit(rel_id, "collector/0")

    relation = generic_charm_harness.model.relations["software-inventory"][0]
    endpoint = SoftwareInventoryProvider(charm=local_charm)

    with pytest.raises(RuntimeError):
        endpoint._update_relation_data(relation)


def test_provider_update_consumers(generic_charm_harness, mocker):
    """Test that Provider's 'update_consumers' function updates data in all related consumers."""
    relation_name = "software-inventory"
    new_port = "10500"
    new_address = "10.255.255.1"
    update_relation_mock = mocker.patch.object(SoftwareInventoryProvider, "_update_relation_data")

    with generic_charm_harness.hooks_disabled():
        generic_charm_harness.add_relation(relation_name, "collector_1")
        generic_charm_harness.add_relation(relation_name, "collector_2")

    expected_update_calls = []
    for relation in generic_charm_harness.model.relations[relation_name]:
        expected_update_calls.append(call(relation))

    endpoint = SoftwareInventoryProvider(charm=generic_charm_harness.charm)
    endpoint.update_consumers(new_port, new_address)

    assert endpoint.port == new_port
    assert endpoint.bound_address == new_address
    update_relation_mock.assert_has_calls(expected_update_calls)


def test_consumer_init():
    """Test initialization of Consumer endpoint."""
    charm = MagicMock()
    relation_name = "s-i-e"
    consumer = SoftwareInventoryConsumer(charm=charm, relation_name=relation_name)

    assert consumer.relation_name == relation_name


def test_consumer_all_exporters(generic_charm_harness):
    """Test Consumer endpoint getting data from all related Providers."""
    remote_units = [f"sw-exporter/{count}" for count in range(5)]
    relation_name = "software-inventory"
    expected_data = []

    with generic_charm_harness.hooks_disabled():
        rel_id = generic_charm_harness.add_relation(relation_name, "sw-exporter")
        for index, unit in enumerate(remote_units):
            generic_charm_harness.add_relation_unit(rel_id, unit)
            unit_data = ExporterConfig(f"10.0.0.{index + 1}", "5000", "test_model")
            generic_charm_harness.update_relation_data(rel_id, unit, asdict(unit_data))
            expected_data.append(unit_data)

    consumer = SoftwareInventoryConsumer(generic_charm_harness.charm, relation_name)

    all_exporters = consumer.all_exporters()
    assert len(all_exporters) == len(expected_data)
    for data in expected_data:
        assert data in all_exporters
