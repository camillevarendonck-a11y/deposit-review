"""Local MCP server: lets Claude analyze the project's deposit CSVs with the same engine
the dashboard uses. Read-only; reads only .csv files inside this folder; no network.

Install once:  pip install mcp  (1.x or 2.x)      Run (stdio):  python3 mcp_server.py
Claude Code finds it through .mcp.json in this folder.
"""
try:  # mcp 2.x renamed FastMCP to MCPServer; support both.
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP
import deposit_tools as tools
from engine import DEFAULT_OBSERVATION, DEFAULT_TARGET

mcp = FastMCP('deposit-review')


@mcp.tool()
def analyze_deposit_file(filename: str = 'deposits.csv', observation_time: str = DEFAULT_OBSERVATION,
                         target_minutes: int = DEFAULT_TARGET) -> dict:
    """Summarize a deposit CSV in this project: target attainment, counts, completed-only median,
    and the hypothetical halved-wait scenario. observation_time is ISO, UTC if no offset."""
    return tools.analyze_file(filename, observation_time, target_minutes)


@mcp.tool()
def review_queue(filename: str = 'deposits.csv', limit: int = 10, observation_time: str = DEFAULT_OBSERVATION,
                 target_minutes: int = DEFAULT_TARGET) -> dict:
    """List the first `limit` records of the investigation queue (most urgent first)."""
    return tools.review_queue(filename, limit, observation_time, target_minutes)


@mcp.tool()
def explain_record(filename: str, deposit_id: str, observation_time: str = DEFAULT_OBSERVATION,
                   target_minutes: int = DEFAULT_TARGET) -> dict:
    """Show one deposit's recorded evidence, timings, status and the rule-based suggested next check."""
    return tools.explain_record(filename, deposit_id, observation_time, target_minutes)


if __name__ == '__main__':
    mcp.run()
