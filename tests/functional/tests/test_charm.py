#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Functional tests for software-inventory-exporter."""

import logging
import time
import unittest

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from zaza import model
from zaza.utilities.juju import get_application_ip

logger = logging.getLogger(__name__)

DPKG_RESPONSE_HEADER_COUNT = 5  # dpkg has 5 lines of header
SNAP_RESPONSE_HEADER_COUNT = 1  # snap has 1 line of header


class SoftwareInventoryExporterTests(unittest.TestCase):
    """Basic functional tests for software-inventory-exporter charm."""

    NAME = "software-inventory-exporter"

    def setUp(self) -> None:
        """Configure resource before tests."""
        self.session = requests.Session()
        self.session.mount(
            "http://", HTTPAdapter(max_retries=Retry(connect=3, backoff_factor=0.5))
        )
        self.endpoint_cmd = {
            "hostname": "hostname",
            "kernel": "uname -r",
            "dpkg": "dpkg -l | wc -l",
            "snap": "snap list | wc -l",
        }

    def get_url(self) -> str:
        """Get the url to be tested."""
        port = model.get_application_config(self.NAME)["port"]["value"]
        ubuntu_ip = get_application_ip("ubuntu")
        return f"http://{ubuntu_ip}:{port}"

    def validate_exporter(self):
        """Confirm that endpoints are working as expected."""
        url = self.get_url()
        for endpoint in self.endpoint_cmd.keys():
            response_exporter = self.session.get(f"{url}/{endpoint}")
            response_ubuntu = (
                model.run_on_leader("ubuntu", self.endpoint_cmd[endpoint]).get("Stdout").strip()
            )
            self.assertTrue(response_exporter.status_code == 200)
            if endpoint == "hostname":
                self.assertEqual(response_exporter.text, response_ubuntu)
            elif endpoint == "kernel":
                content = response_exporter.json()
                self.assertEqual(content[endpoint], response_ubuntu)
            elif endpoint == "dpkg":
                content = response_exporter.json()
                self.assertEqual(len(content), int(response_ubuntu) - DPKG_RESPONSE_HEADER_COUNT)
            elif endpoint == "snap":
                content = response_exporter.json()
                self.assertEqual(len(content), int(response_ubuntu) - SNAP_RESPONSE_HEADER_COUNT)

    def test_exporter(self) -> None:
        """Test that exporter works after port reconfiguration."""
        self.validate_exporter()
        # change port
        port = model.get_application_config(self.NAME)["port"]["value"]
        new_port = port + 2
        logger.info("Setting 'port' config value to %s.", new_port)
        model.set_application_config(self.NAME, {"port": str(new_port)})
        model.block_until_all_units_idle()
        # wait some seconds to server change port
        logger.info("Waiting for server to change port")
        time.sleep(10)
        self.validate_exporter()
