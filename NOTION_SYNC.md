# GitHub to Notion docs mirror

The 29 published MDX pages in this repository have corresponding pages under the CS Harness Notion **Published docs mirror**. The source repository is authoritative. Edit MDX here, then let GitHub Actions update the matching Notion page after a push to `main`.

## One-time setup

1. Create a Notion internal connection with read and update content capabilities in the Notion developer portal. Give it access **only** to the Published docs mirror page and descendants.
2. In this repository, add an Actions repository secret named `NOTION_API_KEY`. Never commit the token or paste it in an issue.
3. Run the **Sync docs to Notion** workflow manually. The first run validates all mapped files and skips unchanged pages. Review the run log and spot-check a table, a code block, and the Studio overview.
4. Merge this PR only after the secret and access are ready; subsequent pushes to MDX on `main` trigger the workflow.

Use `python scripts/notion-docs-sync.py --dry-run` locally to validate the source map without a token. The sync never creates or deletes pages; it updates only the 29 mapped pages. It refuses to overwrite a page without its source blob marker. Mintlify-specific visual components are converted to headings and text. The Notion pages are a content mirror, not a pixel-identical rendering of the site. Manual edits to mirror pages can be replaced by a later source change; edit the MDX source instead. Private Notion pages are outside the map.
