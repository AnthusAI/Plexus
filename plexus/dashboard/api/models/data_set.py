from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List
from plexus.dashboard.api.models.base import BaseModel

if TYPE_CHECKING:
    from plexus.dashboard.api.models.data_source import DataSource

class DataSet(BaseModel):
    _model_name = "DataSet"

    id: str
    name: str
    status: Optional[str]
    source: Optional[str]
    filePath: Optional[str]
    errorMessage: Optional[str]
    createdAt: str
    updatedAt: str
    dataSourceId: str
    dataSource: Optional[DataSource] 