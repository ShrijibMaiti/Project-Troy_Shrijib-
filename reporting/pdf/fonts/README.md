# Fonts

Drop these TTFs here to match the frontend typography:

- `GeneralSans-Regular.ttf`
- `GeneralSans-Semibold.ttf`
- `SometypeMono-Regular.ttf`

Both are free for commercial use (General Sans from Fontshare, Sometype Mono
from Tobias Sonne / Google Fonts). Check the licence file that ships with each
before distributing the PDFs commercially.

**If these files are absent the export still works** — `components.register_fonts()`
falls back to Helvetica and Courier. A missing font must never break an export.

The reason to bother: the exported PDF and the on-screen dashboard should look
like the same object. That coherence does real work in a demo.