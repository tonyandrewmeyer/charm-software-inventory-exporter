# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing
"""Fixture for charm's unit tests."""

import ops.testing
import pytest
from ops.charm import CharmEvents
from ops.framework import EventBase, EventSource

from charm import CharmBase, SoftwareInventoryExporterCharm


class SoftwareInventoryEvents(CharmEvents):
    """Custom event handler for Testing charm."""

    software_inventory_relation_joined = EventSource(EventBase)


class GenericCharm(CharmBase):
    """Generic charm that implements 'on_software_inventory_relation_joined' event.

    This charm is used to test 'software_inventory' library without relying on specific
    implementation of the "main" charm.
    """


@pytest.fixture()
def harness() -> ops.testing.Harness[SoftwareInventoryExporterCharm]:
    """Return harness for SoftwareInventoryExporterCharm."""
    ops.testing.SIMULATE_CAN_CONNECT = True
    harness = ops.testing.Harness(SoftwareInventoryExporterCharm)
    harness.begin()

    yield harness

    harness.cleanup()
    ops.testing.SIMULATE_CAN_CONNECT = False


@pytest.fixture(scope="session")
def model_name() -> str:
    """Preconfigured model named used by 'generic_charm_harness'."""
    return "test_model"


@pytest.fixture()
def generic_charm_harness(model_name) -> ops.testing.Harness[GenericCharm]:
    """Return harness with generic charm that can be used to test 'software-inventory' library."""
    ops.testing.SIMULATE_CAN_CONNECT = True
    harness = ops.testing.Harness(GenericCharm, meta="""
requires:
  software-inventory:
    interface: software-inventory
""")
    harness.set_model_name(model_name)
    harness.begin()

    yield harness

    harness.cleanup()
    ops.testing.SIMULATE_CAN_CONNECT = False
