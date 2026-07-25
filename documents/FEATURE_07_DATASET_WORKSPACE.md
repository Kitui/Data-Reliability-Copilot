# Feature 07 — Dataset Workspace

The Dataset Workspace provides a central registry for datasets used in reliability operations. Users can register datasets, import CSV files, search and filter the registry, review quality status and audit history, maintain ownership and labels, and move directly from a dataset into auditing or issue review.

Dataset records are isolated by workspace and stored in the application database. CSV imports automatically create an audit and register the resulting dataset profile. The page uses the shared full-page router so navigation remains reliable as additional product areas are introduced.


The CSV import action provides visible progress, reports failures directly on the Datasets page, runs an audit automatically, registers the dataset, and selects the resulting registry entry.
