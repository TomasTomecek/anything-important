# Anything important?

Is there an email that requires my attention?

This is a simple tool that periodically checks your gmail inbox for important emails and lets you know via Telegram.

Your inbox is sacred, this is why:
1. This tool uses the least amount of dependencies in case one gets compromised
2. It's meant to be run in a container
3. By default, the tool can access only the Gmail MCP server, nothing else
4. Uses your locally deployed LLM

## How

`anything-important` accesses the official Gmail MCP server.
