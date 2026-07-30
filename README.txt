ESTABLISHMENT MASTER SEARCH — README
=====================================

WHAT THIS IS
------------
A desktop search tool (Python/tkinter) for browsing your EPFO
establishment master download. Loaded with your file, it currently
holds 49,240 establishments.

HOW TO RUN
----------
1. Make sure Python 3 is installed, with these packages:
       pip install pandas openpyxl
   (openpyxl is only needed if you want to export results to .xlsx)

2. Keep "establishment_search.py" and "establishment_master.csv" in
   the same folder.

3. Run:
       python3 establishment_search.py

   On Windows, if tkinter isn't already included with your Python
   install, reinstall Python from python.org and tick "tcl/tk" during
   setup (it's included by default in the standard installer).

WHAT YOU CAN DO
----------------
- Search box: type any text and it searches as you type (with a
  short delay so large searches don't lag). Choose what to search in
  from the "in:" dropdown — All fields, Establishment ID, Name,
  Address, City/District/PIN, PAN/CIN, or LIN Code.

- Filters: narrow by Status (Live/Closed/etc.), District, Industry
  Group, Actionable Status, Establishment Type, or Exemption Status.
  Filters and search combine together (AND logic).

- Click any column heading to sort by that column (click again to
  reverse the order).

- Click a row to see the FULL record (every field from the master
  file, not just the summary columns) in the panel at the bottom.

- "Export Current Results..." saves whatever is currently filtered/
  searched to a new CSV or Excel file — useful for pulling a district-
  wise or status-wise list to work from.

- If a search matches more than 1,500 rows, only the first 1,500 are
  shown in the grid (for speed) — but Export will still save ALL
  matching rows, not just the ones displayed. Narrow your search to
  browse the full match set on-screen.

LOADING A NEWER MASTER FILE
-----------------------------
EPFO establishment master downloads get refreshed periodically. When
you have a newer file:
  File > Load Data File...  and pick the new CSV.
It doesn't need to be renamed — any CSV with the same column
headers as the original download will work.

NOTES
-----
- All data stays on your own computer; nothing is uploaded anywhere.
- The app doesn't modify establishment_master.csv — it only reads it.


MAKING A STANDALONE .EXE (no Python/VS Code needed to RUN it)
================================================================
The app can be packaged into a single .exe (Windows) or standalone
program (Mac/Linux) that runs on any computer of that same type,
even one with no Python installed at all.

IMPORTANT: this packaging step itself has to be done once on a
computer that HAS Python installed, and it has to be done ON THE
SAME TYPE OF COMPUTER you want the final app to run on — a tool
built on Windows only runs on Windows, one built on Linux only runs
on Linux, and so on. This is a limitation of how these packaging
tools work, not a setting. So if your office computer is Windows,
build it on a Windows machine.

STEPS (Windows — most likely what you need):
1. If Python isn't already installed, download it from python.org
   (any recent 3.x version) and install it. During setup, make sure
   "Add python.exe to PATH" is checked.
2. Put these three files in one folder:
     - establishment_search.py
     - establishment_master.csv
     - build_windows.bat
3. Double-click build_windows.bat. It will install the packaging
   tool and build the app automatically (takes a minute or two).
4. When it finishes, look inside the new "dist" folder — you'll
   find EstablishmentMasterSearch.exe there.
5. Copy EstablishmentMasterSearch.exe and establishment_master.csv
   into one folder together (anywhere you like — Desktop, a USB
   drive, another PC). From then on, just double-click the .exe.
   No Python, no VS Code, nothing else needed to run it.

STEPS (Mac/Linux):
   Same idea, but run build_mac_linux.sh instead:
       bash build_mac_linux.sh
   The finished program appears at dist/EstablishmentMasterSearch.

SHARING WITH COLLEAGUES:
Once you've built the .exe, you can copy just the .exe and the CSV
to any other Windows computer and it will run there directly — those
colleagues don't need Python installed at all. If your establishment
master data gets refreshed, just replace the CSV file (same name,
same folder) and reopen the app, or use File > Load Data File inside
the app to point to the new file.
