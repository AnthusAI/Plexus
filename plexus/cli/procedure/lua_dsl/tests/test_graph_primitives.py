"""
Tests for Graph primitives - GraphNodePrimitive and NodeWrapper.

Tests graph-based knowledge representation including:
- Node creation with content and metadata
- Graph navigation (root, current, parent, children)
- Node metadata operations
- Lua table conversion
- Error handling
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from plexus.cli.procedure.lua_dsl.primitives.graph import GraphNodePrimitive, NodeWrapper


class TestGraphNodePrimitive:
    """Test GraphNodePrimitive for graph node operations."""

    @pytest.fixture
    def mock_client(self):
        """Create mock PlexusDashboardClient."""
        client = Mock()
        client.execute = Mock()
        return client

    @pytest.fixture
    def graph_primitive(self, mock_client):
        """Create GraphNodePrimitive for testing."""
        return GraphNodePrimitive(
            client=mock_client,
            procedure_id='proc-123',
            account_id='acct-456'
        )

    @pytest.fixture
    def mock_node(self):
        """Create mock GraphNode."""
        node = Mock()
        node.id = 'node-789'
        node.status = 'ACTIVE'
        node.parentNodeId = None
        node.metadata = {'test': 'data'}
        node.score = None
        node.update_content = Mock()
        return node

    def test_initialization(self, graph_primitive, mock_client):
        """Test GraphNodePrimitive initialization."""
        assert graph_primitive.client == mock_client
        assert graph_primitive.procedure_id == 'proc-123'
        assert graph_primitive.account_id == 'acct-456'
        assert graph_primitive._current_node is None

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_create_node_with_content(self, mock_graphnode_class, graph_primitive, mock_client, mock_node):
        """Test creating a new graph node with content."""
        # Setup mocks
        mock_graphnode_class.create.return_value = mock_node

        # Create node
        result = graph_primitive.create("Test content", {'type': 'test'})

        # Verify GraphNode.create was called correctly
        mock_graphnode_class.create.assert_called_once_with(
            client=mock_client,
            accountId='acct-456',
            procedureId='proc-123',
            parentNodeId=None,
            status='ACTIVE'
        )

        # Verify metadata update
        mock_node.update_content.assert_called_once()
        call_args = mock_node.update_content.call_args
        assert call_args[1]['status'] == 'ACTIVE'
        assert call_args[1]['metadata']['content'] == "Test content"
        assert call_args[1]['metadata']['type'] == 'test'

        # Verify current node was set
        assert graph_primitive._current_node == mock_node

        # Verify NodeWrapper was returned
        assert isinstance(result, NodeWrapper)
        assert result.node == mock_node
        assert result.id == 'node-789'

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_create_node_with_parent(self, mock_graphnode_class, graph_primitive, mock_node):
        """Test creating a child node with parent ID."""
        mock_graphnode_class.create.return_value = mock_node

        result = graph_primitive.create(
            "Child content",
            {'type': 'child'},
            parent_node_id='parent-123'
        )

        # Verify parent ID was passed
        mock_graphnode_class.create.assert_called_once()
        call_args = mock_graphnode_class.create.call_args
        assert call_args[1]['parentNodeId'] == 'parent-123'

        assert isinstance(result, NodeWrapper)

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_create_node_with_lua_table_metadata(self, mock_graphnode_class, graph_primitive, mock_node):
        """Test creating node with Lua table metadata (has .items() method)."""
        mock_graphnode_class.create.return_value = mock_node

        # Simulate Lua table with items() method
        lua_table = Mock()
        lua_table.items.return_value = [('key1', 'value1'), ('key2', 'value2')]

        result = graph_primitive.create("Content", lua_table)

        # Verify metadata was converted from Lua table
        mock_node.update_content.assert_called_once()
        call_args = mock_node.update_content.call_args
        metadata = call_args[1]['metadata']
        assert metadata['key1'] == 'value1'
        assert metadata['key2'] == 'value2'

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_create_node_without_metadata(self, mock_graphnode_class, graph_primitive, mock_node):
        """Test creating node without metadata."""
        mock_graphnode_class.create.return_value = mock_node

        result = graph_primitive.create("Just content")

        # Verify only content was added to metadata
        mock_node.update_content.assert_called_once()
        call_args = mock_node.update_content.call_args
        metadata = call_args[1]['metadata']
        assert metadata == {'content': 'Just content'}

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_create_node_error_handling(self, mock_graphnode_class, graph_primitive):
        """Test error handling during node creation."""
        # Simulate creation error
        mock_graphnode_class.create.side_effect = Exception("Database error")

        result = graph_primitive.create("Content")

        # Should return None on error
        assert result is None

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    def test_root_returns_root_node(self, mock_procedure_class, graph_primitive, mock_client):
        """Test getting the root node for a procedure."""
        # Setup mocks
        mock_procedure = Mock()
        mock_root_node = Mock()
        mock_root_node.id = 'root-node-123'
        mock_root_node.status = 'ACTIVE'
        mock_root_node.parentNodeId = None

        mock_procedure.get_root_node.return_value = mock_root_node
        mock_procedure_class.get_by_id.return_value = mock_procedure

        # Get root node
        result = graph_primitive.root()

        # Verify procedure lookup
        mock_procedure_class.get_by_id.assert_called_once_with('proc-123', mock_client)
        mock_procedure.get_root_node.assert_called_once()

        # Verify NodeWrapper returned
        assert isinstance(result, NodeWrapper)
        assert result.node == mock_root_node
        assert result.id == 'root-node-123'

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    def test_root_returns_none_when_no_root(self, mock_procedure_class, graph_primitive, mock_client):
        """Test root() returns None when no root node exists."""
        mock_procedure = Mock()
        mock_procedure.get_root_node.return_value = None
        mock_procedure_class.get_by_id.return_value = mock_procedure

        result = graph_primitive.root()

        assert result is None

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    def test_root_error_handling(self, mock_procedure_class, graph_primitive):
        """Test error handling when getting root node."""
        mock_procedure_class.get_by_id.side_effect = Exception("Query failed")

        result = graph_primitive.root()

        assert result is None

    def test_current_returns_current_node(self, graph_primitive, mock_node):
        """Test getting the current working node."""
        # Set current node
        graph_primitive._current_node = mock_node

        result = graph_primitive.current()

        assert isinstance(result, NodeWrapper)
        assert result.node == mock_node
        assert result.id == 'node-789'

    def test_current_returns_none_when_not_set(self, graph_primitive):
        """Test current() returns None when no current node."""
        result = graph_primitive.current()
        assert result is None

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_set_current_sets_node(self, mock_graphnode_class, graph_primitive, mock_client, mock_node):
        """Test setting the current working node."""
        mock_graphnode_class.get_by_id.return_value = mock_node

        result = graph_primitive.set_current('node-789')

        # Verify node lookup
        mock_graphnode_class.get_by_id.assert_called_once_with('node-789', mock_client)

        # Verify current node was set
        assert graph_primitive._current_node == mock_node
        assert result is True

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_set_current_error_handling(self, mock_graphnode_class, graph_primitive):
        """Test error handling when setting current node."""
        mock_graphnode_class.get_by_id.side_effect = Exception("Node not found")

        result = graph_primitive.set_current('invalid-node')

        assert result is False
        assert graph_primitive._current_node is None


class TestNodeWrapper:
    """Test NodeWrapper for node methods exposed to Lua."""

    @pytest.fixture
    def mock_client(self):
        """Create mock client."""
        return Mock()

    @pytest.fixture
    def mock_node(self):
        """Create mock GraphNode."""
        node = Mock()
        node.id = 'node-123'
        node.status = 'ACTIVE'
        node.parentNodeId = 'parent-456'
        node.metadata = {'type': 'test', 'score': 0.95}
        node.score = 0.95
        node.update_content = Mock()
        return node

    @pytest.fixture
    def node_wrapper(self, mock_node, mock_client):
        """Create NodeWrapper for testing."""
        return NodeWrapper(mock_node, mock_client)

    def test_initialization(self, node_wrapper, mock_node, mock_client):
        """Test NodeWrapper initialization."""
        assert node_wrapper.node == mock_node
        assert node_wrapper.client == mock_client
        assert node_wrapper.id == 'node-123'
        assert node_wrapper.status == 'ACTIVE'

    def test_initialization_without_status(self, mock_client):
        """Test initialization when node has no status attribute."""
        node = Mock(spec=['id'])
        node.id = 'node-999'

        wrapper = NodeWrapper(node, mock_client)

        assert wrapper.status == 'UNKNOWN'

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_children_returns_child_wrappers(self, mock_graphnode_class, node_wrapper, mock_client):
        """Test getting child nodes."""
        # Setup mock children
        child1 = Mock()
        child1.id = 'child-1'
        child1.status = 'ACTIVE'
        child2 = Mock()
        child2.id = 'child-2'
        child2.status = 'ACTIVE'

        mock_graphnode_class.get_children.return_value = [child1, child2]

        result = node_wrapper.children()

        # Verify get_children was called
        mock_graphnode_class.get_children.assert_called_once_with('node-123', mock_client)

        # Verify NodeWrappers returned
        assert len(result) == 2
        assert all(isinstance(child, NodeWrapper) for child in result)
        assert result[0].id == 'child-1'
        assert result[1].id == 'child-2'

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_children_returns_empty_list_on_error(self, mock_graphnode_class, node_wrapper):
        """Test children() returns empty list on error."""
        mock_graphnode_class.get_children.side_effect = Exception("Query failed")

        result = node_wrapper.children()

        assert result == []

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_parent_returns_parent_wrapper(self, mock_graphnode_class, node_wrapper, mock_client):
        """Test getting parent node."""
        mock_parent = Mock()
        mock_parent.id = 'parent-456'
        mock_parent.status = 'ACTIVE'

        mock_graphnode_class.get_by_id.return_value = mock_parent

        result = node_wrapper.parent()

        # Verify parent lookup
        mock_graphnode_class.get_by_id.assert_called_once_with('parent-456', mock_client)

        # Verify NodeWrapper returned
        assert isinstance(result, NodeWrapper)
        assert result.id == 'parent-456'

    def test_parent_returns_none_for_root(self, mock_client):
        """Test parent() returns None for root node."""
        root_node = Mock()
        root_node.id = 'root-123'
        root_node.status = 'ACTIVE'
        root_node.parentNodeId = None

        wrapper = NodeWrapper(root_node, mock_client)
        result = wrapper.parent()

        assert result is None

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_parent_returns_none_on_error(self, mock_graphnode_class, node_wrapper):
        """Test parent() returns None on error."""
        mock_graphnode_class.get_by_id.side_effect = Exception("Node not found")

        result = node_wrapper.parent()

        assert result is None

    def test_score_returns_node_score(self, node_wrapper):
        """Test getting node score."""
        result = node_wrapper.score()
        assert result == 0.95

    def test_score_returns_none_when_not_set(self, mock_client):
        """Test score() returns None when node has no score."""
        node = Mock(spec=['id', 'status'])
        node.id = 'node-999'
        node.status = 'ACTIVE'

        wrapper = NodeWrapper(node, mock_client)
        result = wrapper.score()

        assert result is None

    def test_metadata_returns_metadata_dict(self, node_wrapper):
        """Test getting node metadata."""
        result = node_wrapper.metadata()
        assert result == {'type': 'test', 'score': 0.95}

    def test_metadata_returns_empty_dict_when_not_set(self, mock_client):
        """Test metadata() returns empty dict when none set."""
        node = Mock(spec=['id', 'status'])
        node.id = 'node-999'
        node.status = 'ACTIVE'

        wrapper = NodeWrapper(node, mock_client)
        result = wrapper.metadata()

        assert result == {}

    def test_metadata_returns_empty_dict_when_none(self, mock_client):
        """Test metadata() returns empty dict when explicitly None."""
        node = Mock()
        node.id = 'node-999'
        node.status = 'ACTIVE'
        node.metadata = None

        wrapper = NodeWrapper(node, mock_client)
        result = wrapper.metadata()

        assert result == {}

    def test_set_metadata_updates_field(self, node_wrapper, mock_node):
        """Test setting a metadata field."""
        result = node_wrapper.set_metadata('status_flag', 'completed')

        # Verify update_content was called with updated metadata
        mock_node.update_content.assert_called_once_with(
            status='ACTIVE',
            metadata={'type': 'test', 'score': 0.95, 'status_flag': 'completed'}
        )

        assert result is True

    def test_set_metadata_creates_dict_if_none(self, mock_client):
        """Test set_metadata creates metadata dict if none exists."""
        node = Mock()
        node.id = 'node-999'
        node.status = 'ACTIVE'
        node.metadata = None
        node.update_content = Mock()

        wrapper = NodeWrapper(node, mock_client)
        result = wrapper.set_metadata('new_key', 'new_value')

        # Verify metadata was created and updated
        node.update_content.assert_called_once_with(
            status='ACTIVE',
            metadata={'new_key': 'new_value'}
        )

        assert result is True

    def test_set_metadata_with_numeric_value(self, node_wrapper, mock_node):
        """Test setting metadata with numeric value."""
        result = node_wrapper.set_metadata('iteration', 42)

        mock_node.update_content.assert_called_once()
        call_args = mock_node.update_content.call_args
        assert call_args[1]['metadata']['iteration'] == 42

        assert result is True

    def test_set_metadata_with_dict_value(self, node_wrapper, mock_node):
        """Test setting metadata with dict value."""
        result = node_wrapper.set_metadata('config', {'model': 'gpt-4', 'temp': 0.7})

        mock_node.update_content.assert_called_once()
        call_args = mock_node.update_content.call_args
        assert call_args[1]['metadata']['config'] == {'model': 'gpt-4', 'temp': 0.7}

        assert result is True

    def test_set_metadata_error_handling(self, node_wrapper, mock_node):
        """Test error handling when setting metadata fails."""
        mock_node.update_content.side_effect = Exception("Update failed")

        result = node_wrapper.set_metadata('key', 'value')

        assert result is False

    def test_repr(self, node_wrapper):
        """Test NodeWrapper string representation."""
        result = repr(node_wrapper)
        assert result == "NodeWrapper(id=node-123, status=ACTIVE)"


class TestGraphNodePrimitiveIntegration:
    """Integration tests for graph operations with realistic scenarios."""

    @pytest.fixture
    def mock_client(self):
        """Create mock client."""
        return Mock()

    @pytest.fixture
    def graph_primitive(self, mock_client):
        """Create GraphNodePrimitive."""
        return GraphNodePrimitive(
            client=mock_client,
            procedure_id='proc-123',
            account_id='acct-456'
        )

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_create_and_navigate_tree(self, mock_graphnode_class, graph_primitive, mock_client):
        """Test creating a tree structure and navigating it."""
        # Create root node
        root = Mock()
        root.id = 'root'
        root.status = 'ACTIVE'
        root.parentNodeId = None
        root.metadata = {'level': 'root'}
        root.update_content = Mock()

        # Create child nodes
        child1 = Mock()
        child1.id = 'child1'
        child1.status = 'ACTIVE'
        child1.parentNodeId = 'root'
        child1.metadata = {'level': 'child'}
        child1.update_content = Mock()

        child2 = Mock()
        child2.id = 'child2'
        child2.status = 'ACTIVE'
        child2.parentNodeId = 'root'
        child2.metadata = {'level': 'child'}
        child2.update_content = Mock()

        # Setup create mock
        mock_graphnode_class.create.side_effect = [root, child1, child2]

        # Create root
        root_wrapper = graph_primitive.create("Root content", {'level': 'root'})
        assert root_wrapper.id == 'root'

        # Create children
        child1_wrapper = graph_primitive.create("Child 1", {'level': 'child'}, 'root')
        child2_wrapper = graph_primitive.create("Child 2", {'level': 'child'}, 'root')

        # Setup navigation mocks
        mock_graphnode_class.get_children.return_value = [child1, child2]
        mock_graphnode_class.get_by_id.return_value = root

        # Navigate tree
        children = root_wrapper.children()
        assert len(children) == 2

        parent = child1_wrapper.parent()
        assert parent.id == 'root'

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    @patch('plexus.dashboard.api.models.procedure.Procedure')
    def test_root_to_children_navigation(self, mock_procedure_class, mock_graphnode_class, graph_primitive, mock_client):
        """Test navigating from root to children."""
        # Setup root node
        root = Mock()
        root.id = 'root'
        root.status = 'ACTIVE'
        root.parentNodeId = None

        # Setup procedure mock
        mock_procedure = Mock()
        mock_procedure.get_root_node.return_value = root
        mock_procedure_class.get_by_id.return_value = mock_procedure

        # Setup children
        child = Mock()
        child.id = 'child'
        child.status = 'ACTIVE'
        mock_graphnode_class.get_children.return_value = [child]

        # Get root and navigate
        root_wrapper = graph_primitive.root()
        assert root_wrapper.id == 'root'

        children = root_wrapper.children()
        assert len(children) == 1
        assert children[0].id == 'child'

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_metadata_operations_workflow(self, mock_graphnode_class, graph_primitive):
        """Test a workflow with metadata operations."""
        # Create node
        node = Mock()
        node.id = 'node-1'
        node.status = 'ACTIVE'
        node.metadata = {}
        node.update_content = Mock()
        mock_graphnode_class.create.return_value = node

        # Create and manipulate
        wrapper = graph_primitive.create("Content", {})

        # Update metadata in sequence
        wrapper.set_metadata('stage', 'processing')
        wrapper.set_metadata('progress', 0.5)
        wrapper.set_metadata('validated', True)

        # Verify all updates were made
        assert node.update_content.call_count == 4  # 1 initial + 3 set_metadata calls

    def test_graph_primitive_repr(self, graph_primitive):
        """Test GraphNodePrimitive string representation."""
        result = repr(graph_primitive)
        assert result == "GraphNodePrimitive(procedure=proc-123)"

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_current_node_workflow(self, mock_graphnode_class, graph_primitive):
        """Test current node workflow (create, check, set)."""
        # Initially no current node
        assert graph_primitive.current() is None

        # Create node sets it as current
        node = Mock()
        node.id = 'node-1'
        node.status = 'ACTIVE'
        node.metadata = {}
        node.update_content = Mock()
        mock_graphnode_class.create.return_value = node

        wrapper = graph_primitive.create("Content")

        # Now current should return the node
        current = graph_primitive.current()
        assert current is not None
        assert current.id == 'node-1'

        # Set different node as current
        node2 = Mock()
        node2.id = 'node-2'
        node2.status = 'ACTIVE'
        mock_graphnode_class.get_by_id.return_value = node2

        success = graph_primitive.set_current('node-2')
        assert success is True

        current = graph_primitive.current()
        assert current.id == 'node-2'


class TestGraphNodeErrorScenarios:
    """Test error scenarios and edge cases."""

    @pytest.fixture
    def mock_client(self):
        """Create mock client."""
        return Mock()

    @pytest.fixture
    def graph_primitive(self, mock_client):
        """Create GraphNodePrimitive."""
        return GraphNodePrimitive(
            client=mock_client,
            procedure_id='proc-123',
            account_id='acct-456'
        )

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_create_node_with_empty_content(self, mock_graphnode_class, graph_primitive):
        """Test creating node with empty content."""
        node = Mock()
        node.id = 'node-1'
        node.status = 'ACTIVE'
        node.metadata = {}
        node.update_content = Mock()
        mock_graphnode_class.create.return_value = node

        result = graph_primitive.create("")

        # Should still create node
        assert result is not None
        # Content should not be in metadata if empty
        node.update_content.assert_called_once()
        call_args = node.update_content.call_args
        assert call_args[1]['metadata'] == {}

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_create_node_with_none_content(self, mock_graphnode_class, graph_primitive):
        """Test creating node with None content."""
        node = Mock()
        node.id = 'node-1'
        node.status = 'ACTIVE'
        node.metadata = {}
        node.update_content = Mock()
        mock_graphnode_class.create.return_value = node

        result = graph_primitive.create(None, {'key': 'value'})

        # Should create node with just metadata
        assert result is not None
        node.update_content.assert_called_once()
        call_args = node.update_content.call_args
        assert 'content' not in call_args[1]['metadata']
        assert call_args[1]['metadata']['key'] == 'value'

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_get_children_with_no_children(self, mock_graphnode_class, mock_client):
        """Test getting children when node has none."""
        node = Mock()
        node.id = 'node-1'
        node.status = 'ACTIVE'

        mock_graphnode_class.get_children.return_value = []

        wrapper = NodeWrapper(node, mock_client)
        children = wrapper.children()

        assert children == []

    def test_node_wrapper_with_missing_client(self):
        """Test NodeWrapper behavior with None client."""
        node = Mock()
        node.id = 'node-1'
        node.status = 'ACTIVE'
        node.parentNodeId = 'parent-1'

        wrapper = NodeWrapper(node, None)

        # Should still be able to get id and status
        assert wrapper.id == 'node-1'
        assert wrapper.status == 'ACTIVE'

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_parent_lookup_with_invalid_parent_id(self, mock_graphnode_class, mock_client):
        """Test parent lookup when parent ID is invalid."""
        node = Mock()
        node.id = 'child'
        node.status = 'ACTIVE'
        node.parentNodeId = 'invalid-parent'

        mock_graphnode_class.get_by_id.side_effect = Exception("Not found")

        wrapper = NodeWrapper(node, mock_client)
        parent = wrapper.parent()

        # Should return None on error
        assert parent is None

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_update_metadata_preserves_existing(self, mock_graphnode_class, graph_primitive):
        """Test that set_metadata preserves existing metadata."""
        node = Mock()
        node.id = 'node-1'
        node.status = 'ACTIVE'
        node.metadata = {'existing': 'data', 'count': 10}
        node.update_content = Mock()
        mock_graphnode_class.create.return_value = node

        wrapper = graph_primitive.create("Content", {'existing': 'data', 'count': 10})

        # Update with new key
        wrapper.set_metadata('new_field', 'new_value')

        # Verify existing metadata preserved
        call_args = node.update_content.call_args_list[-1]  # Last call
        metadata = call_args[1]['metadata']
        assert metadata['existing'] == 'data'
        assert metadata['count'] == 10
        assert metadata['new_field'] == 'new_value'

    @patch('plexus.dashboard.api.models.graph_node.GraphNode')
    def test_create_node_json_serialization(self, mock_graphnode_class, graph_primitive):
        """Test that metadata is properly JSON serialized."""
        import json

        node = Mock()
        node.id = 'node-1'
        node.status = 'ACTIVE'
        node.metadata = {}
        node.update_content = Mock()
        mock_graphnode_class.create.return_value = node

        # Create with complex metadata
        complex_metadata = {
            'string': 'value',
            'number': 42,
            'float': 3.14,
            'bool': True,
            'null': None,
            'list': [1, 2, 3],
            'nested': {'key': 'value'}
        }

        wrapper = graph_primitive.create("Content", complex_metadata)

        # Verify metadata structure is preserved
        node.update_content.assert_called_once()
        call_args = node.update_content.call_args
        metadata = call_args[1]['metadata']

        # Ensure it can be JSON serialized
        json_str = json.dumps(metadata)
        assert isinstance(json_str, str)

        # Ensure it can be deserialized back
        restored = json.loads(json_str)
        assert restored['string'] == 'value'
        assert restored['number'] == 42
        assert restored['nested']['key'] == 'value'
