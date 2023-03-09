#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""
import logging
import os
from typing import Optional, Union

import yaml
from charms.operator_libs_linux.v1 import snap
from charms.software_inventory_exporter.v0.software_inventory import SoftwareInventoryProvider
from ops.charm import (
    CharmBase,
    ConfigChangedEvent,
    InstallEvent,
    UpdateStatusEvent,
    UpgradeCharmEvent,
)
from ops.framework import Framework
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, ModelError

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class SoftwareInventoryExporterCharm(CharmBase):
    """Software Inventory Exporter charm."""

    EXPORTER_SNAP_NAME = "software-inventory-exporter"
    EXPORTER_CONF = f"/var/snap/{EXPORTER_SNAP_NAME}/current/config.yaml"
    EXPORTER_SERVICE = f"snap.{EXPORTER_SNAP_NAME}.{EXPORTER_SNAP_NAME}.service"

    def __init__(self, framework: Framework) -> None:
        """Initialize charm."""
        super().__init__(framework)
        self.snaps = snap.SnapCache()

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_install)
        self.framework.observe(self.on.update_status, self._on_update_status)

        self.provider_endpoint = SoftwareInventoryProvider(
            charm=self,
            bound_address=self.config["bind_address"],
            port=str(self.config["port"]),
        )

    @property
    def snap_path(self) -> Optional[str]:
        """Get local path to exporter snap.

        If this charm has snap file for the exporter attached as a resource, this property returns
        path to the snap file. If the resource was not attached or the file is empty, this property
        returns None.
        """
        try:
            snap_path = str(self.model.resources.fetch("exporter-snap"))
            # Don't return path to empty resource file
            if not os.path.getsize(snap_path) > 0:
                return None
        except ModelError:
            return None

        return snap_path

    @property
    def exporter(self) -> snap.Snap:
        """Return Snap object representing Software Inventory Exporter snap."""
        return self.snaps[self.EXPORTER_SNAP_NAME]

    def _on_install(self, _: Union[InstallEvent, UpgradeCharmEvent]) -> None:
        """Install Software Inventory Exporter snap.

        Snap can be installed either from local resource or from Snapstore.
        """
        if self.snap_path:
            snap.install_local(self.snap_path, dangerous=True, classic=True)
        else:
            snap.ensure(
                snap_names=self.EXPORTER_SNAP_NAME,
                classic=True,
                state=str(snap.SnapState.Latest),
            )

        self.reconfigure_exporter()
        self.assess_status()

    def _on_config_changed(self, _: ConfigChangedEvent) -> None:
        """Update exporter configuration and update related applications."""
        port = self.config["port"]
        address = self.config["bind_address"]

        self.reconfigure_exporter()
        self.provider_endpoint.update_consumers(str(port), address)
        self.assess_status()

    def _on_update_status(self, _: UpdateStatusEvent) -> None:
        """Trigger unit's status assessment."""
        self.assess_status()

    def reconfigure_exporter(self) -> None:
        """Render new exporter config and restart its service."""
        self.render_exporter_config()
        self.exporter.restart()

    def render_exporter_config(self) -> None:
        """Generate new exporter config based on the charm config and save it to file."""
        settings = {
            "bind_address": self.config["bind_address"],
            "port": int(self.config["port"]),
        }
        config = {"settings": settings}
        with open(self.EXPORTER_CONF, "w", encoding="UTF-8") as conf_file:
            yaml.safe_dump(config, conf_file)

    def assess_status(self) -> None:
        """Set charm status based on the status of the exporter service."""
        if self.is_exporter_running():
            self.unit.status = ActiveStatus("Unit is ready.")
        else:
            self.unit.status = BlockedStatus("Exporter service is not running.")
            logger.error(
                "Exporter service %s is not running. Latest logs from the service:\n%s",
                self.EXPORTER_SERVICE,
                self.exporter.logs(num_lines=20),
            )

    def is_exporter_running(self) -> bool:
        """Return true if exporter's service is running."""
        return self.exporter.services[self.EXPORTER_SNAP_NAME]["active"]


if __name__ == "__main__":  # pragma: nocover
    main(SoftwareInventoryExporterCharm)
