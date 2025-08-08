from abc import ABC, abstractmethod
from pydantic import BaseModel, ValidationError, Field
from plexus.CustomLogging import logging

class DataCache(ABC):
    """
    A data cache is responsible for loading data from a source and caching it locally.  This is an
    abstract base class that defines the interface and the parameter validation schema.  Subclasses
    are responsible for implementing the actual data loading logic.  Most subclasses will also need
    to extend the `Parameters` class to define any necessary parameters for getting the data.
    """

    class Parameters(BaseModel):
        """
        Parameters for data caching.  Override this class to define any necessary parameters for
        getting the data.

        Attributes
        ----------
        class : str
            The name of the data cache class.
        """
        # "class" is a reserved keyword in Python, so we use "class_name" instead.
        class_name: str = Field(alias='class', default='DataCache')
            
    def __init__(self, **parameters):
        """
        Initialize the DataCache instance with the given parameters.

        Parameters
        ----------
        **parameters : dict
            Arbitrary keyword arguments that are used to initialize the Parameters instance.

        Raises
        ------
        ValidationError
            If the provided parameters do not pass validation.
        """
        try:
            self.parameters = self.Parameters(**parameters)
            logging.info("Initializing [magenta1][b]DataCache[/b][/magenta1]")
        except ValidationError as e:
            DataCache.log_validation_errors(e)
            raise

    def log_validation_errors(error: ValidationError):
        """
        Log validation errors for the parameters.

        Parameters
        ----------
        error : ValidationError
            The validation error object containing details about the validation failures.
        """
        error_messages = []
        for error_detail in error.errors():
            field = ".".join(str(loc) for loc in error_detail["loc"])
            message = error_detail["msg"]
            error_messages.append(f"Field: {field}, Error: {message}")

        logging.error("Parameter validation errors occurred:")
        for message in error_messages:
            logging.error(message)

    def upsert_item_for_dataset_row(self, dashboard_client, account_id, item_data, identifiers_dict, external_id=None, score_id=None):
        """
        Common method to upsert an Item for a dataset row.
        This centralizes Item creation logic that was duplicated across subclasses.
        
        Args:
            dashboard_client: PlexusDashboardClient instance
            account_id: The account ID
            item_data: Dict or object containing item information (id, description, etc.)
            identifiers_dict: Dict of identifier key-value pairs for the item
            external_id: Optional external ID for the item (defaults to item_data.id)
            score_id: Optional score ID to associate with the Item
            
        Returns:
            Tuple[str, bool, str]: (item_id, was_created, error_msg)
        """
        try:
            from plexus.dashboard.api.models.item import Item
            
            # Determine external ID
            if not external_id:
                if hasattr(item_data, 'id'):
                    external_id = item_data.id
                elif hasattr(item_data, 'externalId'):
                    external_id = item_data.externalId
                elif isinstance(item_data, dict):
                    external_id = item_data.get('id') or item_data.get('externalId')
            
            # Determine description
            description = None
            if hasattr(item_data, 'description'):
                description = item_data.description
            elif isinstance(item_data, dict):
                description = item_data.get('description')
            
            if not description and external_id:
                description = f"Dataset Item - {external_id}"
            
            # Extract text and metadata from item_data if available
            text = None
            metadata = None
            if hasattr(item_data, 'text'):
                text = item_data.text
            elif isinstance(item_data, dict):
                text = item_data.get('text')
                
            if hasattr(item_data, 'metadata'):
                metadata = item_data.metadata
            elif isinstance(item_data, dict):
                metadata = item_data.get('metadata')
            
            # If metadata is already a JSON string, convert it to dict for Item.upsert_by_identifiers
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    # If it's not valid JSON, leave it as a string
                    pass
            
            # Upsert the Item with identifiers and score association
            return Item.upsert_by_identifiers(
                client=dashboard_client,
                account_id=account_id,
                identifiers=identifiers_dict,
                external_id=str(external_id) if external_id else None,
                description=description,
                text=text or "",
                metadata=metadata,
                is_evaluation=False,  # Dataset items are not evaluation items
                score_id=score_id,  # Associate with score if provided
                debug=True
            )
            
        except Exception as e:
            error_msg = f"Failed to upsert item: {str(e)}"
            logging.error(error_msg)
            return None, False, error_msg

    def debug_dataframe(self, df, context="DATAFRAME", logger=None):
        """
        Essential debug logging for dataframes.
        
        Args:
            df: pandas DataFrame to analyze
            context: String identifier for the context (used in log messages)
            logger: Logger instance to use (defaults to module logger)
        """
        if logger is None:
            logger = logging
        
        # Essential dataset info
        logger.info(f"{context}: {df.shape[0]} rows x {df.shape[1]} columns")
        logger.info(f"Columns: {list(df.columns)}")
        
        # Show first 3 rows sample
        if len(df) > 0:
            logger.info("Sample data (first 3 rows):")
            for i in range(min(3, len(df))):
                row_data = {}
                for col in df.columns:
                    value = df.iloc[i][col]
                    if isinstance(value, str) and len(value) > 100:
                        row_data[col] = value[:97] + "..."
                    else:
                        row_data[col] = value
                logger.info(f"  Row {i}: {row_data}")

    @abstractmethod
    def load_dataframe(self, *args, **kwargs):
        """
        Load a dataframe based on the provided parameters.

        Returns
        -------
        pd.DataFrame
            The loaded dataframe.
        This method must be implemented by all subclasses.
        """
        pass