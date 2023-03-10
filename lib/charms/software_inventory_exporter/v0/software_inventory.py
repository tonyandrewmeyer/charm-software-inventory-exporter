"""
# Software Inventory relation library.

You may find this library useful if you want to relate with 'Software Inventory
Exporter' charm to simplify interaction with the relation data. This library provides
implementation for both sides of the relation:

- SoftwareInventoryProvider - This is a 'Provide' side, and you probably don't need to
worry about it if you are not re-implementing the exporter charm itself
- SoftwareInventoryConsumer - This is a 'Require' side, and it simplifies access to the
relation data provided by the other side.

A simple example of 'SoftwareInventoryConsumer' usage:

```python
# ...
from charms.software_inventory_exporter.v0.software_inventory import SoftwareInventoryConsumer
from ops.charm import RelationEvent

class MyCharm(CharmBase):
    def __init__(self, *args):
        # ...
        # This is your name of the relation that implements 'software-inventory' interface
        relation_name = "my-software-inventory"
        self.software_inventory_exporter = SoftwareInventoryConsumer(self, relation_name)
        self.framework.observe(self.on[relation_name]_relation_changed, self._on_exporter_change)
        # ...

    def _on_exporter_change(self, _: RelationEvent) -> None:
        for exporter in self.software_inventory_exporter.all_exporters():
            endpoint = f"{exporter.hostname}:{exporter.port}"
            print(f"I'm related to exporter in model {exporter.model} listening on {endpoint}")
```
You can file bugs [here](https://github.com/canonical/charm-software-inventory-exporter/issues)!
"""
import socket
from dataclasses import asdict, dataclass
from typing import List

from ops.charm import CharmBase, RelationJoinedEvent
from ops.framework import Object
from ops.model import Relation

# The unique Charmhub library identifier, never change it
LIBID = "4c763405b08940639004664e878beaf2"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

DEFAULT_RELATION_NAME = "software-inventory"


@dataclass
class ExporterConfig:
    """Representation of an exporter configuration.

    Consumer side of the relation can rely on the fact that each related exporter
    (Provider side) configured these properties in the relation data.
    """

    hostname: str
    port: str
    model: str
    ingress_ip: str = ""


class SoftwareInventoryConsumer(Object):
    """Consumer is on the 'Require' side of 'software-inventory relation'."""

    def __init__(self, charm: CharmBase, relation_name: str = DEFAULT_RELATION_NAME) -> None:
        """Initialize Consumer ('Require') Endpoint."""
        super().__init__(charm, None)
        self.charm = charm
        self.relation_name = relation_name

    def all_exporters(self) -> List[ExporterConfig]:
        """Return configuration of all related Software Inventory Exporters.

        This configuration can be used to set up collector to scrape data from every
        exporter.
        """
        exporter_configs = []
        provider_relations = self.model.relations[self.relation_name]

        for relation in provider_relations:
            for unit in relation.units:
                remote_data = relation.data[unit]
                ingress = remote_data.get("ingress-address") or remote_data.get("private-address")
                exporter_configs.append(
                    ExporterConfig(
                        port=remote_data["port"],
                        hostname=remote_data["hostname"],
                        model=remote_data["model"],
                        ingress_ip=ingress,
                    )
                )

        return exporter_configs


class SoftwareInventoryProvider(Object):
    """Implementation of to 'Provider' side of 'software-inventory' relation."""

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = DEFAULT_RELATION_NAME,
        bound_address: str = "0.0.0.0",
        port: str = "8675",
    ) -> None:
        """Initialize Provider Endpoint."""
        super().__init__(charm, None)
        self.charm = charm
        self.relation_name = relation_name
        self._port = port
        self._bound_address = bound_address
        self.framework.observe(charm.on[relation_name].relation_joined, self._on_consumer_joined)

    @property
    def port(self) -> str:
        """Port on which the Software Inventory Exporter is listening."""
        return self._port

    @property
    def bound_address(self) -> str:
        """Address on which the Software Inventory Exporter is listening."""
        return self._bound_address

    def _on_consumer_joined(self, event: RelationJoinedEvent) -> None:
        """Set relation data when unit with 'Require' side of the relation joins."""
        self._update_relation_data(event.relation)

    def _update_relation_data(self, relation: Relation) -> None:
        """Update data in a single relation according to the current config."""
        host = socket.gethostname()
        relation_data = ExporterConfig(model=self.model.name, hostname=host, port=self.port)
        relation.data[self.charm.unit].update(asdict(relation_data))

    def update_consumers(self, port: str, bound_address: str) -> None:
        """Update relation data in every related unit according to the current config.

        :param port: New value of the port on which the exporter is listening
        :param bound_address: New value of the address on which the exporter is listening
        :return: None
        """
        self._port = port
        self._bound_address = bound_address
        consumer_relations = self.model.relations[self.relation_name]

        for relation in consumer_relations:
            self._update_relation_data(relation)
