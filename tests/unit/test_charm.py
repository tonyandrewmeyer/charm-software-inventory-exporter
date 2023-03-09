# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing
"""Unit tests for src/charm.py module."""
from unittest.mock import MagicMock, PropertyMock, mock_open, patch

import pytest

import charm


@pytest.mark.parametrize("resource_size", [0, 100])
def test_snap_path_property(resource_size, harness, mocker):
    """Test that `snap_path` property returns path only if valid resource is attached."""
    true_path_to_resource = "/path/to/resource"
    expected_path = true_path_to_resource if resource_size else None
    mocker.patch.object(harness.charm.model.resources, "fetch", return_value=true_path_to_resource)
    mocker.patch.object(charm.os.path, "getsize", return_value=resource_size)

    assert harness.charm.snap_path == expected_path


def test_snap_path_property_not_attached(harness, mocker):
    """Test that `snap_path` property returns path only if valid resource is attached."""
    mocker.patch.object(harness.charm.model.resources, "fetch", side_effect=charm.ModelError)
    mocker.patch.object(charm.os.path, "getsize")

    assert harness.charm.snap_path is None


def test_exporter_property(harness):
    """Test that 'exporter' property returns exporter 'Snap' object."""
    exporter_snap = MagicMock()
    harness.charm.snaps = {harness.charm.EXPORTER_SNAP_NAME: exporter_snap}

    assert harness.charm.exporter == exporter_snap


@patch.object(charm.SoftwareInventoryExporterCharm, "snap_path", PropertyMock)
@pytest.mark.parametrize("local_snap_path", [None, "path/to/resource.snap"])
def test_on_install_local_resource(local_snap_path, harness, mocker):
    """Test _on_install method.

    Two scenarios are tested:
      * Snap is installed from local resource file
      * Snap is installed from Snapstore
    """
    harness.charm.snap_path = local_snap_path
    install_local_mock = mocker.patch.object(charm.snap, "install_local")
    install_from_store_mock = mocker.patch.object(charm.snap, "ensure")
    reconfigure_mock = mocker.patch.object(harness.charm, "reconfigure_exporter")
    assess_status_mock = mocker.patch.object(harness.charm, "assess_status")

    harness.charm._on_install(MagicMock())

    if local_snap_path is None:
        install_local_mock.assert_not_called()
        install_from_store_mock.assert_called_once_with(
            snap_names=harness.charm.EXPORTER_SNAP_NAME,
            classic=True,
            state=str(charm.snap.SnapState.Latest),
        )
    else:
        install_from_store_mock.assert_not_called()
        install_local_mock.assert_called_once_with(local_snap_path, dangerous=True, classic=True)

    reconfigure_mock.assert_called_once()
    assess_status_mock.assert_called_once()


def test_snap_config(harness, mocker):
    """Test charm's reaction to config change."""
    reconfigure_exporter_mock = mocker.patch.object(harness.charm, "reconfigure_exporter")
    update_relation_mock = mocker.patch.object(harness.charm.provider_endpoint, "update_consumers")
    assess_status_mock = mocker.patch.object(harness.charm, "assess_status")

    new_port = 10099
    new_address = "10.0.0.10"
    harness.update_config({"port": new_port, "bind_address": new_address})

    reconfigure_exporter_mock.assert_called_once()
    update_relation_mock.assert_called_once_with(str(new_port), new_address)
    assess_status_mock.assert_called_once()


@patch.object(charm.SoftwareInventoryExporterCharm, "exporter", PropertyMock)
def test_reconfigure_exporter(harness, mocker):
    """Test helper function that updates config and restarts exporter service."""
    render_config_mock = mocker.patch.object(harness.charm, "render_exporter_config")
    exporter_snap = MagicMock()
    harness.charm.exporter = exporter_snap

    harness.charm.reconfigure_exporter()

    render_config_mock.assert_called_once()
    exporter_snap.restart.assert_called_once()


def test_render_exporter_config(harness, mocker):
    """Test function that renders exporter's configuration file."""
    yaml_dump_mock = mocker.patch.object(charm.yaml, "safe_dump")
    expected_config = {
        "settings": {
            "bind_address": harness.charm.config.get("bind_address"),
            "port": harness.charm.config.get("port"),
        }
    }

    open_file_function = mock_open()
    with patch("builtins.open", open_file_function) as file_open_mock:
        harness.charm.render_exporter_config()
        file_open_mock.assert_called_once_with(harness.charm.EXPORTER_CONF, "w", encoding="UTF-8")

    yaml_dump_mock.assert_called_once_with(expected_config, open_file_function())


@patch.object(
    charm.SoftwareInventoryExporterCharm, "exporter", PropertyMock(return_value=MagicMock())
)
@pytest.mark.parametrize(
    "service_running, expected_state", [(True, charm.ActiveStatus), (False, charm.BlockedStatus)]
)
def test_assess_status(service_running, expected_state, harness, mocker):
    """Test function that sets the final status of the unit."""
    mocker.patch.object(harness.charm, "is_exporter_running", return_value=service_running)

    harness.charm.assess_status()

    assert isinstance(harness.charm.unit.status, expected_state)


@patch.object(charm.SoftwareInventoryExporterCharm, "exporter", new_callable=PropertyMock)
@pytest.mark.parametrize("exporter_running", [True, False])
def test_is_exporter_running(exporter, exporter_running, harness):
    """Test helper method that returns whether the exporter service is running or not."""
    service_map = {harness.charm.EXPORTER_SNAP_NAME: {"active": exporter_running}}
    exporter_snap_mock = PropertyMock()
    exporter_snap_mock.services = service_map
    exporter.return_value = exporter_snap_mock

    assert harness.charm.is_exporter_running() == exporter_running


def test_on_update_status(harness, mocker):
    """Test that _on_update method triggers unit status assessment."""
    assess_status_mock = mocker.patch.object(harness.charm, "assess_status")

    harness.charm._on_update_status(MagicMock())

    assess_status_mock.assert_called_once()
