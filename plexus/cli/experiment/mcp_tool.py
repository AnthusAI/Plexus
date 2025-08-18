"""
MCP Tool wrapper for LangChain compatibility.

Provides a simple wrapper that makes MCP tools compatible with LangChain's tool interface.
"""

from typing import Dict, Any, Optional, Callable
from pydantic import BaseModel


class MCPTool(BaseModel):
    """LangChain-compatible tool that wraps an MCP tool."""
    name: str
    description: str
    args_schema: Optional[type] = None
    func: Callable[[Dict[str, Any]], str]
    
    def run(self, **kwargs) -> str:
        """Run the tool with the given arguments."""
        return self.func(kwargs)
    
    async def arun(self, **kwargs) -> str:
        """Async version of run."""
        return self.run(**kwargs)

