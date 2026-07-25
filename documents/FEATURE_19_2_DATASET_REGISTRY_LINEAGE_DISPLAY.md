# Feature 19.2 — Dataset Registry Lineage Display

## Overview
The Dataset Registry now represents each dataset as one lineage row and exposes the latest imported version directly in the registry.

## Registry behavior
- One dataset lineage remains one registry row.
- Importing a new version updates the existing row.
- The row shows the latest version number and source filename.
- Older revisions remain available in Dataset Versions.

## Backend
Dataset list and detail responses now include `latest_version` and `latest_source_filename`, derived from workspace-scoped audit history and the latest upload.

## UX
The dataset detail panel also shows the latest version and latest source file. Static assets were bumped to version 0.19.2.
