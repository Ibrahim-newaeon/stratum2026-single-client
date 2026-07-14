"""
Knowledge Graph Service

Main service for interacting with the Stratum Knowledge Graph.
Provides high-level APIs for graph operations and revenue analytics.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    EdgeLabel,
    GraphEdge,
    GraphNode,
    NodeLabel,
)
from .queries import CypherQueryBuilder, RevenueAnalyticsQueries

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """
    Service for managing the Stratum Knowledge Graph.

    Provides:
    - CRUD operations for graph nodes and edges
    - Revenue attribution queries
    - Trust gate decision tracing
    - Customer journey analysis
    - Integration with CDP and Trust Engine

    Usage:
        async with get_db_session() as session:
            kg = KnowledgeGraphService(session)

            # Create a profile node
            profile = ProfileNode(
                external_id=profile_id,
                lifecycle_stage=LifecycleStage.CUSTOMER
            )
            await kg.create_node(profile)

            # Query revenue attribution
            results = await kg.get_revenue_by_channel(days=30)
    """

    GRAPH_NAME = "stratum_knowledge_graph"

    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # NODE OPERATIONS
    # =========================================================================

    async def create_node(self, node: GraphNode) -> dict[str, Any]:
        """
        Create a new node in the knowledge graph.

        Args:
            node: GraphNode instance (ProfileNode, EventNode, etc.)

        Returns:
            Created node properties from the graph
        """
        properties = node.to_cypher_properties()
        label = node.label

        query = CypherQueryBuilder().build_create_node(
            alias="n", node_label=NodeLabel(label), properties=properties
        )

        result = await self.session.execute(text(query))
        row = result.fetchone()

        if row:
            return self._parse_agtype(row[0])
        return {}

    async def merge_node(
        self, node: GraphNode, match_fields: list[str] = None
    ) -> dict[str, Any]:
        """
        Merge (upsert) a node - create if not exists, update if exists.

        Args:
            node: GraphNode instance
            match_fields: Fields to match on (default: external_id)

        Returns:
            Merged node properties
        """
        match_fields = match_fields or ["external_id"]
        properties = node.to_cypher_properties()

        match_props = {k: properties[k] for k in match_fields if k in properties}
        set_props = {k: v for k, v in properties.items() if k not in match_fields}

        query = CypherQueryBuilder().build_merge_node(
            alias="n",
            node_label=NodeLabel(node.label),
            match_properties=match_props,
            set_properties=set_props,
        )

        result = await self.session.execute(text(query))
        row = result.fetchone()

        if row:
            return self._parse_agtype(row[0])
        return {}

    async def get_node(
        self, label: NodeLabel, external_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Get a node by its external ID.

        Args:
            label: Node label (Profile, Event, etc.)
            external_id: External system ID

        Returns:
            Node properties or None if not found
        """
        query, _params = (
            CypherQueryBuilder()
            .match_node("n", label, {"external_id": external_id})
            .return_fields(["n"])
            .limit(1)
            .build()
        )

        result = await self.session.execute(text(query))
        row = result.fetchone()

        if row:
            return self._parse_agtype(row[0])
        return None

    async def delete_node(self, label: NodeLabel, external_id: str) -> bool:
        """
        Delete a node and its relationships.

        Args:
            label: Node label
            external_id: External system ID

        Returns:
            True if deleted, False if not found
        """
        cypher = f"""
            MATCH (n:{label.value} {{external_id: '{external_id}'}})
            DETACH DELETE n
            RETURN count(n) AS deleted
        """
        query = f"""
            SELECT * FROM cypher('{self.GRAPH_NAME}', $$
                {cypher}
            $$) AS (result agtype);
        """

        result = await self.session.execute(text(query))
        row = result.fetchone()

        if row:
            deleted = self._parse_agtype(row[0])
            return deleted.get("deleted", 0) > 0
        return False

    # =========================================================================
    # EDGE OPERATIONS
    # =========================================================================

    async def create_edge(
        self,
        edge: GraphEdge,
        start_label: NodeLabel,
        start_external_id: str,
        end_label: NodeLabel,
        end_external_id: str,
    ) -> dict[str, Any]:
        """
        Create an edge between two nodes.

        Args:
            edge: GraphEdge instance
            start_label: Label of source node
            start_external_id: External ID of source node
            end_label: Label of target node
            end_external_id: External ID of target node

        Returns:
            Created edge properties
        """
        query = CypherQueryBuilder().build_create_edge(
            start_label=start_label,
            start_match={
                "external_id": start_external_id,
            },
            edge_label=edge.label,
            end_label=end_label,
            end_match={
                "external_id": end_external_id,
            },
            edge_properties=edge.to_cypher_properties(),
        )

        result = await self.session.execute(text(query))
        row = result.fetchone()

        if row:
            return self._parse_agtype(row[0])
        return {}

    async def get_edges(
        self,
        start_label: NodeLabel,
        start_external_id: str,
        edge_label: Optional[EdgeLabel] = None,
    ) -> list[dict[str, Any]]:
        """
        Get all edges from a node.

        Args:
            start_label: Source node label
            start_external_id: Source node external ID
            edge_label: Optional filter by edge type

        Returns:
            List of edge and target node properties
        """
        edge_filter = f":{edge_label.value}" if edge_label else ""

        cypher = f"""
            MATCH (n:{start_label.value} {{external_id: '{start_external_id}'}})
                  -[r{edge_filter}]->(m)
            RETURN type(r) AS relationship, properties(r) AS edge_props, labels(m) AS target_labels, properties(m) AS target_props
        """
        query = f"""
            SELECT * FROM cypher('{self.GRAPH_NAME}', $$
                {cypher}
            $$) AS (result agtype);
        """

        result = await self.session.execute(text(query))
        edges = []
        for row in result:
            edges.append(self._parse_agtype(row[0]))
        return edges

    # =========================================================================
    # REVENUE ANALYTICS
    # =========================================================================

    async def get_revenue_by_channel(self, days: int = 30) -> list[dict[str, Any]]:
        """
        Get revenue breakdown by acquisition channel.

        Args:
            days: Lookback period in days

        Returns:
            List of channel revenue data
        """
        query, _params = RevenueAnalyticsQueries.revenue_by_channel(days)
        result = await self.session.execute(text(query))

        return [self._parse_agtype(row[0]) for row in result]

    async def get_revenue_by_campaign(
        self, platform: Optional[str] = None, days: int = 30
    ) -> list[dict[str, Any]]:
        """
        Get revenue breakdown by campaign.

        Args:
            platform: Optional platform filter (meta, google, etc.)
            days: Lookback period in days

        Returns:
            List of campaign revenue data with ROAS
        """
        query, _params = RevenueAnalyticsQueries.revenue_by_campaign(platform, days)
        result = await self.session.execute(text(query))

        return [self._parse_agtype(row[0]) for row in result]

    async def get_customer_journey(self, profile_external_id: str) -> dict[str, Any]:
        """
        Get complete customer journey for a profile.

        Args:
            profile_external_id: Profile's external ID

        Returns:
            Journey data with events and revenue
        """
        query, _params = RevenueAnalyticsQueries.customer_journey(profile_external_id)
        result = await self.session.execute(text(query))
        row = result.fetchone()

        if row:
            return self._parse_agtype(row[0])
        return {}

    async def get_segment_revenue_performance(
        self, days: int = 30
    ) -> list[dict[str, Any]]:
        """
        Get revenue performance by customer segment.

        Args:
            days: Lookback period in days

        Returns:
            List of segment performance data
        """
        query, _params = RevenueAnalyticsQueries.segment_revenue_performance(days)
        result = await self.session.execute(text(query))

        return [self._parse_agtype(row[0]) for row in result]

    async def get_rfm_segment_distribution(self) -> list[dict[str, Any]]:
        """
        Get RFM segment distribution and revenue contribution.

        Returns:
            List of RFM segment data
        """
        query, _params = RevenueAnalyticsQueries.rfm_segment_trends()
        result = await self.session.execute(text(query))

        return [self._parse_agtype(row[0]) for row in result]

    # =========================================================================
    # TRUST ENGINE ANALYTICS
    # =========================================================================

    async def get_blocked_automations(self, days: int = 7) -> list[dict[str, Any]]:
        """
        Get automations that were blocked by trust gates.

        Args:
            days: Lookback period in days

        Returns:
            List of blocked automation data with reasons
        """
        query, _params = RevenueAnalyticsQueries.blocked_automations(days)
        result = await self.session.execute(text(query))

        return [self._parse_agtype(row[0]) for row in result]

    async def get_signal_health_impact(self, days: int = 30) -> list[dict[str, Any]]:
        """
        Analyze correlation between signal health and revenue.

        Args:
            days: Lookback period in days

        Returns:
            Signal health vs revenue correlation data
        """
        query, _params = RevenueAnalyticsQueries.signal_health_impact(days)
        result = await self.session.execute(text(query))

        return [self._parse_agtype(row[0]) for row in result]

    async def trace_automation_decision(
        self, automation_external_id: str
    ) -> dict[str, Any]:
        """
        Trace the full decision path for an automation.

        Shows: Signal -> TrustGate -> Automation -> Outcome

        Args:
            automation_external_id: Automation's external ID

        Returns:
            Full decision trace with all related nodes
        """
        cypher = f"""
            MATCH (a:Automation {{external_id: '{automation_external_id}'}})
            OPTIONAL MATCH (s:Signal)-[:EVALUATED_BY]->(tg:TrustGate)-[decision:TRIGGERED|BLOCKED]->(a)
            OPTIONAL MATCH (a)-[:PRODUCED]->(r:Revenue)
            RETURN {{
                automation: properties(a),
                signals: collect(DISTINCT properties(s)),
                trust_gate: properties(tg),
                decision_type: type(decision),
                revenue_produced: collect(DISTINCT properties(r))
            }} AS trace
        """
        query = f"""
            SELECT * FROM cypher('{self.GRAPH_NAME}', $$
                {cypher}
            $$) AS (result agtype);
        """

        result = await self.session.execute(text(query))
        row = result.fetchone()

        if row:
            return self._parse_agtype(row[0])
        return {}

    # =========================================================================
    # ATTRIBUTION ANALYTICS
    # =========================================================================

    async def get_multi_touch_paths(
        self, min_touchpoints: int = 2, limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        Get multi-touch attribution paths to conversion.

        Args:
            min_touchpoints: Minimum touchpoints in path
            limit: Maximum results

        Returns:
            List of attribution paths with revenue
        """
        query, _params = RevenueAnalyticsQueries.multi_touch_attribution_paths(
            min_touchpoints, limit
        )
        result = await self.session.execute(text(query))

        return [self._parse_agtype(row[0]) for row in result]

    async def get_channel_transition_matrix(self, days: int = 30) -> list[dict[str, Any]]:
        """
        Get channel-to-channel transition probabilities for Markov attribution.

        Args:
            days: Lookback period

        Returns:
            List of channel transitions with counts
        """
        cypher = f"""
            MATCH (p:Profile)-[:RECEIVED]->(t1:Touchpoint)
            MATCH (p)-[:RECEIVED]->(t2:Touchpoint)
            WHERE t2.timestamp > t1.timestamp
              AND t2.timestamp < t1.timestamp + duration({{days: 7}})
            WITH t1.channel AS from_channel, t2.channel AS to_channel, count(*) AS transitions
            RETURN from_channel, to_channel, transitions
            ORDER BY transitions DESC
            LIMIT 100
        """
        query = f"""
            SELECT * FROM cypher('{self.GRAPH_NAME}', $$
                {cypher}
            $$) AS (result agtype);
        """

        result = await self.session.execute(text(query))
        return [self._parse_agtype(row[0]) for row in result]

    # =========================================================================
    # GRAPH STATISTICS
    # =========================================================================

    async def get_graph_stats(self) -> dict[str, Any]:
        """
        Get overall graph statistics.

        Returns:
            Node and edge counts by type
        """
        stats = {}

        # Count each node type
        for label in NodeLabel:
            cypher = f"""
                MATCH (n:{label.value})
                RETURN count(n) AS count
            """
            query = f"""
                SELECT * FROM cypher('{self.GRAPH_NAME}', $$
                    {cypher}
                $$) AS (result agtype);
            """
            result = await self.session.execute(text(query))
            row = result.fetchone()
            if row:
                data = self._parse_agtype(row[0])
                stats[f"{label.value.lower()}_count"] = data.get("count", 0)

        # Count edges
        for edge in EdgeLabel:
            cypher = f"""
                MATCH ()-[r:{edge.value}]->()
                RETURN count(r) AS count
            """
            query = f"""
                SELECT * FROM cypher('{self.GRAPH_NAME}', $$
                    {cypher}
                $$) AS (result agtype);
            """
            result = await self.session.execute(text(query))
            row = result.fetchone()
            if row:
                data = self._parse_agtype(row[0])
                stats[f"{edge.value.lower()}_edges"] = data.get("count", 0)

        return stats

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    @staticmethod
    def _parse_agtype(value: Any) -> Any:
        """Parse Apache AGE agtype to Python dict."""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                # AGE returns JSON-like strings
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        if isinstance(value, dict):
            return value
        return value

    async def execute_cypher(self, cypher: str) -> list[dict[str, Any]]:
        """
        Execute a raw Cypher query.

        WARNING: Use with caution. Prefer typed methods.

        Args:
            cypher: Raw Cypher query

        Returns:
            List of result rows
        """
        logger.info(f"Executing raw Cypher: {cypher[:100]}...")

        query = f"""
            SELECT * FROM cypher('{self.GRAPH_NAME}', $$
                {cypher}
            $$) AS (result agtype);
        """

        result = await self.session.execute(text(query))
        return [self._parse_agtype(row[0]) for row in result]

    async def health_check(self) -> bool:
        """
        Check if the knowledge graph is accessible.

        Returns:
            True if graph is healthy
        """
        try:
            query = f"""
                SELECT * FROM cypher('{self.GRAPH_NAME}', $$
                    RETURN 1 AS health
                $$) AS (result agtype);
            """
            result = await self.session.execute(text(query))
            row = result.fetchone()
            return row is not None
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error("knowledge_graph_health_check_failed", error=str(e))
            return False
