'''Unit tests for the item command-line interface.'''
import unittest
from unittest.mock import MagicMock, patch
from pyfakefs.fake_filesystem_unittest import TestCase
from plexus.cli.item_logic import _process_item_folder, resolve_item, insert_items, upsert_items, delete_item
from plexus.dashboard.api.models.item import Item
from plexus.dashboard.api.models.identifier import Identifier
from datetime import datetime

class TestItemCommands(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.mock_client = MagicMock()

        # --- Mock Item Data ---
        self.item_id = "item-123"
        self.account_id = "acc-456"
        self.evaluation_id = "eval-789"
        self.external_id = "ext-abc"
        self.folder_path = "items/test-item-1"
        self.identifier_value = "CUST-XYZ"

        # --- Fake Filesystem Setup ---
        self.fs.create_dir(self.folder_path)
        self.fs.create_file(
            f"{self.folder_path}/text.txt", 
            contents="This is the item text."
        )
        self.fs.create_file(
            f"{self.folder_path}/metadata.json",
            contents='{"source": "test", "priority": 1}'
        )
        self.fs.create_file(
            f"{self.folder_path}/identifiers.yaml",
            contents='''- name: CustomerID
  value: CUST-XYZ
  url: http://example.com/cust/XYZ
'''
        )
        self.fs.create_file(f"{self.folder_path}/attachment.log", contents="log data")

    def test_process_item_folder_json(self):
        """Test processing an item folder with JSON metadata and identifiers."""
        self.fs.remove_object(f"{self.folder_path}/metadata.json")
        self.fs.remove_object(f"{self.folder_path}/identifiers.yaml")
        self.fs.create_file(
            f"{self.folder_path}/metadata.json",
            contents='{"source": "json_test"}'
        )
        self.fs.create_file(
            f"{self.folder_path}/identifiers.json",
            contents='[{"name": "jsonID", "value": "123"}]'
        )

        item_data = _process_item_folder(self.folder_path)
        self.assertEqual(item_data['metadata']['source'], 'json_test')
        self.assertEqual(item_data['identifiers'][0]['name'], 'jsonID')

    def test_process_item_folder_yaml(self):
        """Test processing an item folder with YAML metadata and identifiers."""
        self.fs.remove_object(f"{self.folder_path}/metadata.json")
        self.fs.remove_object(f"{self.folder_path}/identifiers.yaml")
        self.fs.create_file(
            f"{self.folder_path}/metadata.yaml",
            contents='source: yaml_test'
        )
        self.fs.create_file(
            f"{self.folder_path}/identifiers.yaml",
            contents='- name: yamlID\n  value: 456'
        )

        item_data = _process_item_folder(self.folder_path)
        self.assertEqual(item_data['metadata']['source'], 'yaml_test')
        self.assertEqual(item_data['identifiers'][0]['name'], 'yamlID')

    def test_process_item_folder_missing_files(self):
        """Test processing a folder with missing optional files."""
        folder_path = "items/empty-item"
        self.fs.create_dir(folder_path)

        item_data = _process_item_folder(folder_path)
        self.assertIsNone(item_data['text'])
        self.assertEqual(item_data['metadata'], {})
        self.assertEqual(item_data['identifiers'], [])

    def test_resolve_item_by_id(self):
        """Test resolving an item by its direct ID."""
        with patch('plexus.dashboard.api.models.item.Item.get_by_id') as mock_get_by_id:
            mock_get_by_id.return_value = Item(
                id=self.item_id, accountId=self.account_id, evaluationId=self.evaluation_id,
                createdAt=datetime.now(), updatedAt=datetime.now(), isEvaluation=False
            )
            
            item = resolve_item(self.mock_client, self.account_id, self.item_id)
            self.assertIsNotNone(item)
            self.assertEqual(item.id, self.item_id)
            mock_get_by_id.assert_called_once_with(self.item_id, self.mock_client)

    def test_resolve_item_by_external_id(self):
        """Test resolving an item by its external ID."""
        with patch('plexus.dashboard.api.models.item.Item.get_by_id') as mock_get_by_id:
            mock_get_by_id.return_value = None
            self.mock_client.execute.return_value = {
                'itemsByAccountIdAndExternalId': {
                    'items': [
                        {
                            'id': self.item_id, 
                            'accountId': self.account_id, 
                            'externalId': self.external_id, 
                            'evaluationId': self.evaluation_id,
                            'createdAt': datetime.now().isoformat(), 
                            'updatedAt': datetime.now().isoformat(),
                            'isEvaluation': False
                        }
                    ]
                }
            }

            item = resolve_item(self.mock_client, self.account_id, self.external_id)
            self.assertIsNotNone(item)
            self.assertEqual(item.externalId, self.external_id)

    def test_resolve_item_by_identifier(self):
        """Test resolving an item using an identifier."""
        with patch('plexus.dashboard.api.models.item.Item.get_by_id') as mock_get_by_id:
            mock_get_by_id.side_effect = [Exception("Item not found"), Item(
                id=self.item_id, accountId=self.account_id, evaluationId=self.evaluation_id,
                createdAt=datetime.now(), updatedAt=datetime.now(), isEvaluation=False
            )]
            self.mock_client.execute.return_value = {'itemsByAccountIdAndExternalId': {'items': []}} # No external ID match
            
            with patch('plexus.dashboard.api.models.identifier.Identifier.find_by_value') as mock_find_by_value:
                mock_find_by_value.return_value = Identifier(
                    itemId=self.item_id, name='CustomerID', value=self.identifier_value, 
                    accountId=self.account_id, createdAt=datetime.now(), updatedAt=datetime.now()
                )

                item = resolve_item(self.mock_client, self.account_id, self.identifier_value)
                self.assertIsNotNone(item)
                self.assertEqual(item.id, self.item_id)
                mock_find_by_value.assert_called_once_with(self.identifier_value, self.account_id, self.mock_client)

    def test_insert_item_with_all_data(self):
        """Test inserting an item with text, metadata, identifiers, and attachments."""
        with patch('plexus.dashboard.api.models.item.Item.create') as mock_create:
            mock_create.return_value = Item(
                id=self.item_id, accountId=self.account_id, evaluationId=self.evaluation_id,
                createdAt=datetime.now(), updatedAt=datetime.now(), isEvaluation=False
            )

            results = insert_items(
                self.mock_client, self.account_id, self.folder_path, self.evaluation_id, None, False
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['status'], 'success')
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            self.assertEqual(call_kwargs['text'], "This is the item text.")
            self.assertEqual(call_kwargs['metadata']['source'], 'test')
            self.assertIn({'name': 'folderPath', 'value': self.folder_path}, call_kwargs['identifiers'])

    def test_upsert_item_insert_and_update(self):
        """Test upserting an item that does not yet exist, then updating it."""
        # Insert
        with patch('plexus.cli.item_logic.resolve_item') as mock_resolve, \
             patch('plexus.dashboard.api.models.item.Item.create') as mock_create:
            
            mock_resolve.return_value = None
            mock_create.return_value = Item(
                id=self.item_id, accountId=self.account_id, evaluationId=self.evaluation_id,
                createdAt=datetime.now(), updatedAt=datetime.now(), isEvaluation=False
            )

            results = upsert_items(
                self.mock_client, self.account_id, self.folder_path, self.evaluation_id, None, False
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['status'], 'inserted')
            mock_create.assert_called_once()

        # Update
        mock_existing_item = MagicMock(spec=Item)
        mock_existing_item.id = self.item_id
        with patch('plexus.cli.item_logic.resolve_item') as mock_resolve, \
             patch.object(mock_existing_item, 'update') as mock_update:

            mock_resolve.return_value = mock_existing_item
            mock_update.return_value = mock_existing_item

            results = upsert_items(
                self.mock_client, self.account_id, self.folder_path, self.evaluation_id, None, False
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['status'], 'updated')
            mock_update.assert_called_once()

    def test_delete_item(self):
        """Test deleting an item."""
        mock_item = MagicMock(spec=Item)
        mock_item.id = self.item_id
        mock_item.delete = MagicMock()

        with patch('plexus.cli.item_logic.resolve_item') as mock_resolve:
            
            mock_resolve.return_value = mock_item

            delete_item(self.mock_client, self.account_id, self.item_id)
            mock_item.delete.assert_called_once()

if __name__ == '__main__':
    unittest.main()
