"""Atlan REST API client for asset search, lineage, and documentation lookup.

Uses the Atlan index search API (Elasticsearch-based) to find data assets
and retrieve ownership, lineage, and documentation.

Requires ATLAN_BASE_URL and ATLAN_API_TOKEN in .env.
"""

import os
import requests


class AtlanClient:
    def __init__(self, base_url: str = None, api_token: str = None):
        self.base_url = (base_url or os.getenv("ATLAN_BASE_URL", "https://workiva.atlan.com")).rstrip("/")
        self.token = api_token or os.getenv("ATLAN_API_TOKEN", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/meta{path}"

    def search_assets(self, query: str, asset_types: list[str] = None, limit: int = 10) -> list[dict]:
        """Search for assets by name or keyword.

        Args:
            query: Search term (table name, model name, keyword)
            asset_types: Filter by type (e.g., ["Table", "View", "DbtModel", "Column"])
            limit: Max results to return

        Returns list of dicts with: name, qualifiedName, typeName, guid, owners, description, url
        """
        dsl = {
            "query": {
                "bool": {
                    "must": [
                        {"multi_match": {
                            "query": query,
                            "fields": ["name", "qualifiedName", "description"],
                            "type": "best_fields",
                        }},
                    ],
                    "filter": [
                        {"term": {"__state": "ACTIVE"}},
                    ],
                },
            },
            "size": limit,
            "sort": [{"_score": {"order": "desc"}}],
        }

        if asset_types:
            dsl["query"]["bool"]["filter"].append(
                {"terms": {"__typeName.keyword": asset_types}}
            )

        payload = {
            "dsl": dsl,
            "attributes": [
                "name", "qualifiedName", "description", "ownerUsers", "ownerGroups",
                "certificateStatus", "connectionName", "databaseName", "schemaName",
                "userDescription", "readme",
            ],
        }

        resp = self.session.post(self._url("/search/indexsearch"), json=payload)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for entity in data.get("entities", []):
            attrs = entity.get("attributes", {})
            results.append({
                "name": attrs.get("name", ""),
                "qualified_name": attrs.get("qualifiedName", ""),
                "type": entity.get("typeName", ""),
                "guid": entity.get("guid", ""),
                "owners": attrs.get("ownerUsers", []) or [],
                "owner_groups": attrs.get("ownerGroups", []) or [],
                "description": attrs.get("description") or attrs.get("userDescription") or "",
                "certificate": attrs.get("certificateStatus", ""),
                "connection": attrs.get("connectionName", ""),
                "database": attrs.get("databaseName", ""),
                "schema": attrs.get("schemaName", ""),
                "url": self.asset_url(entity.get("guid", "")),
            })
        return results

    def get_lineage(self, guid: str, depth: int = 1, direction: str = "BOTH") -> dict:
        """Get lineage for an asset by GUID.

        Args:
            guid: Asset GUID from search results
            depth: How many hops to traverse (1 = immediate neighbors)
            direction: "INPUT" (upstream), "OUTPUT" (downstream), or "BOTH"

        Returns dict with upstream and downstream asset lists.
        """
        params = {"depth": depth, "direction": direction}
        resp = self.session.get(self._url(f"/lineage/{guid}"), params=params)
        resp.raise_for_status()
        data = resp.json()

        base_entity_guid = data.get("baseEntityGuid", guid)
        relations = data.get("relations", [])
        guid_entity_map = data.get("guidEntityMap", {})

        # Build adjacency: base -> process -> table/view
        # Upstream: entities that feed into the base (via process nodes)
        # Downstream: entities that the base feeds into
        from_map = {}  # to_guid -> [from_guids]
        to_map = {}    # from_guid -> [to_guids]
        for rel in relations:
            f = rel.get("fromEntityId", "")
            t = rel.get("toEntityId", "")
            from_map.setdefault(t, []).append(f)
            to_map.setdefault(f, []).append(t)

        def collect_reachable(start_guid, follow_map, skip_types=("Process", "DbtProcess", "ColumnProcess", "BIProcess")):
            visited = set()
            queue = [start_guid]
            results = []
            while queue:
                current = queue.pop(0)
                for neighbor in follow_map.get(current, []):
                    if neighbor in visited or neighbor == base_entity_guid:
                        continue
                    visited.add(neighbor)
                    entity = guid_entity_map.get(neighbor, {})
                    if entity.get("typeName", "") in skip_types:
                        queue.append(neighbor)
                    else:
                        results.append({
                            "name": entity.get("displayText", "") or entity.get("attributes", {}).get("name", ""),
                            "type": entity.get("typeName", ""),
                            "guid": neighbor,
                            "url": self.asset_url(neighbor),
                        })
            return results

        upstream = collect_reachable(base_entity_guid, from_map)
        downstream = collect_reachable(base_entity_guid, to_map)

        return {"upstream": upstream, "downstream": downstream}

    def get_asset(self, guid: str) -> dict:
        """Get full asset details by GUID."""
        resp = self.session.get(self._url(f"/entity/guid/{guid}"),
                                params={"ignoreRelationships": "false"})
        resp.raise_for_status()
        return resp.json()

    def asset_url(self, guid: str) -> str:
        """Construct a browsable Atlan URL for an asset."""
        if not guid:
            return ""
        return f"{self.base_url}/assets/{guid}/overview"

    def search_tables(self, name: str, limit: int = 5) -> list[dict]:
        """Search for tables and views by name."""
        return self.search_assets(name, asset_types=["Table", "View", "MaterialisedView", "SnowflakeDynamicTable"], limit=limit)

    def search_models(self, name: str, limit: int = 5) -> list[dict]:
        """Search for dbt models by name."""
        return self.search_assets(name, asset_types=["DbtModel"], limit=limit)
