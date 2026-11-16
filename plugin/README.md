# social-analytics — Claude plugin

Bundles two things:

- **`social-analytics` skill** (`skills/social-analytics/SKILL.md`): teaches Claude when to use each tool, how to keep Apify spend down, how to read engagement and sentiment numbers correctly, and how to format creator comparisons and sponsorship vetting reports.
- **The MCP server** (`.mcp.json`): launched with `uvx` straight from this GitHub repo, so users don't need to clone anything.

## Install (Claude Code)

Prerequisites: [`uv`](https://docs.astral.sh/uv/) installed, and an [Apify](https://apify.com) API token.

1. Put your Apify token in your shell environment (e.g. in `~/.zshrc`), then restart your terminal:

   ```bash
   export APIFY_API_TOKEN=your_apify_token
   ```

2. In Claude Code, add the marketplace and install the plugin:

   ```
   /plugin marketplace add animeshgaur25/social-analytics-mcp
   /plugin install social-analytics@social-analytics
   ```

3. Restart Claude Code. Check with `/mcp` that `social-analytics-mcp` is connected.

Then just ask: *"Run a full audit on @cristiano"*, *"Compare @MrBeast and @mkbhd on YouTube engagement"*, *"Is @eminem safe to sponsor?"*. The skill loads automatically when the question is about a creator's performance.

Team-wide: commit this to your project's `.claude/settings.json` so teammates are prompted to install it:

```json
{
  "extraKnownMarketplaces": {
    "social-analytics": {
      "source": { "source": "github", "repo": "animeshgaur25/social-analytics-mcp" }
    }
  },
  "enabledPlugins": { "social-analytics@social-analytics": true }
}
```

## Install (Claude.ai / Claude Desktop, skill only)

1. Zip the skill folder: `cd plugin/skills && zip -r social-analytics.zip social-analytics`
2. In Claude, go to **Settings → Capabilities → Skills**, upload `social-analytics.zip`, and enable it.
3. Connect the MCP server separately — either the stdio config in the main README, or a deployed Cloud Run URL (`https://<service>/mcp`) added as a custom connector.

The skill is only useful when the MCP server is connected; without it Claude will tell the user the tools are missing.

## Updating

Bump `version` in `.claude-plugin/plugin.json` and push. Users run `/plugin marketplace update social-analytics`.
