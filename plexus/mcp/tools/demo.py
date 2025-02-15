"""Demo task tool for testing MCP functionality."""

import asyncio
import logging
from typing import Optional

from mcp.server.fastmcp import Context
from mcp.types import TextContent

logger = logging.getLogger(__name__)

class DemoTaskTool:
    """A demo tool that simulates a long-running task with progress updates."""

    def __init__(self, total_items: int = 10, target_duration: float = 5.0, fail: bool = False):
        """Initialize the demo task tool.
        
        Args:
            total_items: The total number of items to process.
            target_duration: The target duration in seconds.
            fail: Whether to fail the task.
        """
        self.total_items = total_items
        self.target_duration = target_duration
        self.fail = fail
        self.description = "A demo tool that simulates a long-running task with progress updates"

    async def execute(
        self,
        ctx: Context,
        total_items: Optional[int] = None,
        target_duration: Optional[float] = None,
        fail: Optional[bool] = None,
    ) -> TextContent:
        """Execute the demo task.
        
        Args:
            ctx: The execution context.
            total_items: Override the default total items.
            target_duration: Override the default target duration.
            fail: Override whether to fail the task.
            
        Returns:
            A text content response with the task result.
        """
        total = total_items if total_items is not None else self.total_items
        duration = target_duration if target_duration is not None else self.target_duration
        should_fail = fail if fail is not None else self.fail

        delay_per_item = duration / total

        await ctx.info(f"Starting demo task with {total} items over {duration} seconds")

        for i in range(total):
            if should_fail and i == total // 2:
                await ctx.error("Task failed halfway through")
                raise RuntimeError("Task failed halfway through")

            await asyncio.sleep(delay_per_item)
            await ctx.report_progress(i + 1, total)
            await ctx.info(f"Processed item {i + 1}/{total}")

        await ctx.info("Task completed successfully")
        return TextContent(text="Demo task completed successfully")