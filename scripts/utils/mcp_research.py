"""MCP-based research adapter.

Connects to one or more MCP servers (declared in `mcp_servers.json`), discovers
their tools, runs them to gather facts about an athlete, and returns the
aggregated text. The research agent can then feed that into the LLM as
*authoritative* context — instead of relying solely on the model's training data.

Pattern matches the Anthropic Python SDK reference:
  https://github.com/modelcontextprotocol/python-sdk

Configuration — drop a JSON file at `mcp_servers.json` in the project root:

[
  {
    "name": "fetch",
    "command": "uvx",
    "args": ["mcp-server-fetch"]
  },
  {
    "name": "brave_search",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "env": { "BRAVE_API_KEY": "your-key" }
  },
  {
    "name": "wikipedia",
    "command": "uvx",
    "args": ["mcp-server-wikipedia"]
  }
]

Env override: set `MCP_SERVERS_JSON=/path/to/file` to point elsewhere.

If `mcp` isn't installed or no servers are configured, `enrich()` returns "" —
the existing research agent still runs as before.
"""
from __future__ import annotations
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("neverquit.mcp")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "mcp_servers.json"


def _config_path() -> Path:
    return Path(os.getenv("MCP_SERVERS_JSON") or DEFAULT_CONFIG)


def is_enabled() -> bool:
    """True if `mcp` is importable AND a config file exists."""
    try:
        import mcp  # noqa: F401
    except Exception:
        return False
    return _config_path().exists()


def _load_servers() -> list[dict]:
    p = _config_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as e:
        log.warning("MCP config parse failed: %s", e)
        return []


# ---------- Async core (uses official mcp SDK) ----------

async def _query_one_server(spec: dict, queries: list[str]) -> list[dict]:
    """Connect to one MCP server, list its tools, call relevant ones with each
    query, and return tool results.

    Tools are matched by simple keyword: any tool with name/description
    containing 'search', 'fetch', 'web', 'wikipedia', 'browse', or 'lookup'
    is considered useful for athlete research.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    name = spec.get("name", spec.get("command", "mcp"))
    params = StdioServerParameters(
        command=spec.get("command", "uvx"),
        args=spec.get("args", []),
        env={**os.environ, **(spec.get("env") or {})},
    )

    out: list[dict] = []
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_resp = await session.list_tools()
                tools = list(tools_resp.tools)
                useful = [
                    t for t in tools
                    if any(k in (t.name + " " + (t.description or "")).lower()
                           for k in ("search", "fetch", "web", "wikipedia",
                                     "browse", "lookup", "summary"))
                ]
                if not useful:
                    log.info("MCP %s: no useful tools (had %s)", name,
                             [t.name for t in tools])
                    return out

                # Try the first useful tool for each query.
                tool = useful[0]
                first_arg = next(iter((tool.inputSchema or {}).get("properties", {})), "query")

                for q in queries:
                    try:
                        result = await session.call_tool(tool.name, {first_arg: q})
                        # Flatten content to plain strings.
                        chunks = []
                        for c in (result.content or []):
                            text = getattr(c, "text", None)
                            if text:
                                chunks.append(text)
                        if chunks:
                            out.append({
                                "server": name,
                                "tool": tool.name,
                                "query": q,
                                "text": "\n".join(chunks)[:4000],  # cap each entry
                            })
                    except Exception as e:
                        log.warning("MCP %s tool=%s query=%r failed: %s",
                                    name, tool.name, q, e)
    except Exception as e:
        log.warning("MCP %s connect failed: %s", name, e)
    return out


async def _enrich_async(athlete_name: str, sport: str) -> list[dict]:
    servers = _load_servers()
    if not servers:
        return []
    queries = [
        f"{athlete_name} {sport} biography",
        f"{athlete_name} comeback story Paralympics Olympics",
        f"{athlete_name} interview quotes coach training",
    ]
    tasks = [_query_one_server(s, queries) for s in servers]
    nested = await asyncio.gather(*tasks, return_exceptions=True)
    flat: list[dict] = []
    for n in nested:
        if isinstance(n, list):
            flat.extend(n)
    return flat


# ---------- Public sync API ----------

def enrich(athlete_name: str, sport: str = "", timeout: int = 60) -> str:
    """Returns a single text blob of MCP-gathered context, or "" if disabled.

    Drop this string into the research prompt as `{mcp_context}` so the LLM
    has authoritative facts to work from.
    """
    if not is_enabled():
        return ""
    try:
        coro = asyncio.wait_for(_enrich_async(athlete_name, sport), timeout=timeout)
        results = asyncio.run(coro)
    except Exception as e:
        log.warning("MCP enrichment failed: %s", e)
        return ""
    if not results:
        return ""
    blob = []
    for r in results:
        blob.append(f"### Source: {r['server']} · tool: {r['tool']} · query: {r['query']}\n{r['text']}")
    return "\n\n".join(blob)
