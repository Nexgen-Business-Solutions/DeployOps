# Default Cashmatic reference files

Place the actual files here using these names. Missing files are simply skipped;
do not create empty PDFs or images.

| Filename | Reference |
| --- | --- |
| `user-manual.pdf` | Self Pay 460 user manual |
| `web-interface.pdf` | Web panel interface |
| `my-cashmatic-app.pdf` | My Cashmatic App explanation |
| `device-installation-guide.pdf` | CDIG |
| `parts-manual.pdf` | Self Pay 460 user manual with the parts ("For more clarification about SP460 parts") |
| `device-configuration.pdf` | F1 configuration reference |
| `user-setup.pdf` | F2 user setup reference |
| `warnings-precautions.pdf` | Warnings and precautions (on-site installation) |
| `logo.png` | Company logo / labeling image |
| `bellabot-deployment-manual.pdf` | BellaBot Pro deployment manual |
| `bellabot-operation-guide.pdf` | BellaBot Pro operation guide |
| `bellabot-product-introduction.pdf` | BellaBot Pro product introduction |
| `bellabot-maintenance-and-care.png` | BellaBot Pro maintenance and care (image in the Jotform) |

These are filename placeholders, not verified source mappings. Rename/relabel as
needed when the references are confirmed. Only include distribution-approved
reference materials, never completed customer forms or credentials.

On installation and after every migrate, the files found here become private attachments in **DeployOps
Reference Files** (search for it in Desk), each listed in the pre-installation
and on-site sections where the Jotforms showed it. Missing files are skipped. A file can be
listed in several sections; it is uploaded once.

The same happens after every `bench migrate` (the `after_migrate` hook), so a site
that already has the app gets the references of a new release without anyone
running a command. Each bundled reference is added once per site: the hidden
field *Seeded references* remembers what was added, so a row an administrator
deletes is not added again, and a row already listed (same checklist and section,
same title or file) is not duplicated.
If the list can't be saved during a migrate (for example a row whose section no
longer exists), the migrate still finishes: nothing is added, the error is in
the **Error Log**, and the next migrate tries again once the row is fixed.

DeployOps Administrators maintain the list afterwards: upload, replace, give each
file a **Title**, and choose the **Checklist** and **Section** (the section's
field name, e.g. `machine_activation_steps_section`; empty = top of the
checklist). Migrations never change or remove their rows.

Technicians see each file as a card with a first-page preview under its section,
and open it in the app's page-by-page viewer (see docs/FRONTEND.md). The files
stay private: only users with a DeployOps role can open them.

The mapping of each file to the original Jotforms is in
docs/CASHMATIC_PREINSTALLATION_MAPPING.md §3, docs/CASHMATIC_INSTALLATION_MAPPING.md §3, docs/BELLABOT_PREINSTALLATION_MAPPING.md §3 and docs/BELLABOT_INSTALLATION_MAPPING.md §3.
