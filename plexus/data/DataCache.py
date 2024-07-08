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
        class_name: str = Field(alias='class')

        class Config:
            allow_population_by_field_name = True
            
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