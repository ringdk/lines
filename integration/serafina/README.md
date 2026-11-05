# Serafina integration

Everything Serafina needs from Lines lives here, in this repo, not in
hers: nothing in her code names it (serafina/docs/APPS.md, rule 10).

| | |
|---|---|
| `lines.md` | The skill: when to use the tools, and how. Loaded through `skill_dirs`. |

A persona is optional, and only for an app where a character fits beside it
(her §58.3); most apps have none. If this one does, put `<id>.persona.md` here
(her §50.12), list it in `serafina-app.toml` (`personas = ["<id>"]`) and add
`personas: [<id>]` to the `apps:` entry below: her chat panel beside the app
then starts with it.

## Wiring it up

Three entries in her `config/serafina.yaml`. Her secrets `LINES_APP_KEY` and
`LINES_MCP_TOKEN` come from `lines-admin web-key` and `lines-admin
mcp-token` ([docs/deploy-astarte.md](../../docs/deploy-astarte.md), which has
the commands that add these).

```yaml
# Lines's pages, inside her, behind her sign-in (her §52).
apps:
  - name: lines
    title: Lines
    upstream: http://127.0.0.1:8794/ui
    secret: LINES_APP_KEY
    icon: app                     # one of the names her apps row draws (§52)
    users: [ringdk@gmail.com]

# Its tools, with her bearer token and who each call is for.
mcp_servers:
  - name: lines
    url: http://127.0.0.1:8794/mcp
    auth: bearer
    token_secret: LINES_MCP_TOKEN
    tool_prefix: ""               # the tools already name themselves lines_*
    enabled: true
    untrusted: true               # results carry what people wrote: her untrusted fence
    pass_context: true            # _serafina on every call: user_email is checked
    app: lines               # lines_open shows its pages (§55)

# The skill, from the deployed checkout rather than copied into hers.
skill_dirs:
  - /opt/lines/integration/serafina
```

Restart her backend (`scripts/reload.sh`) for the config; the skill
hot-reloads after that.

## Removing Lines

Delete the three entries and reload her. She keeps working: the skill stops
loading, the tools stop registering, the app leaves her apps row.
