 ClassiCompass 🧭

ClassiCompass is a premium, dark-themed web platform built for vintage and classic literature enthusiasts. It allows readers to load historical workspaces, sync up for group reading sessions, log advanced terminology, and share live, "Locket-style" visual snapshots of their reading environments.
🎨 Core Features

*   **Dynamic Art Canopy Header:** Seamlessly integrates with the Metropolitan Museum of Art Open REST API to dynamically rotate and showcase classic oil painting masterpieces on the backdrop.
*   **Live Reading Grid (Locket-style Widget):** An interactive media dashboard feed where logged-in community members can snap, upload, and beam real-time atmospheric visual photos of their book chapters directly to the homepage dashboard.
*   **Dialogue Thread Hub:** A dedicated repository room discussion forum layout where circle members can drop thematic notes, analysis hooks, and structural findings in real-time.
*   **Vocabulary Vault:** A secure personal relational logging module for indexing and archiving complex vocabulary definitions encountered while reading.
*   **Targeted Search Indexing:** Restricts book curation to pre-1960 releases via integration checks to keep focus strictly on pure historical classics.
 💻 Tech Stack

- **Backend Architecture:** Python (Flask Engine)
- **Database Storage Management:** SQLite3 (Relational Schema)
- **Frontend Presentation Layer:** HTML5, Custom CSS3 Grid Specs, Responsive Inline Vector SVGs
- **Third-Party Open APIs:** The Metropolitan Museum of Art API & OpenLibrary Database API
⚙️ Local Installation & Setup

Want to run ClassiCompass locally on your machine? Follow these quick execution steps:
1. Clone the Workspace
```bash
git clone [https://github.com/1MV23CS075/ClassiCompass.git](https://github.com/1MV23CS075/ClassiCompass.git)
pip install flask requests werkzeug
python app.py
Once the terminal starts the execution loop, open your web browser and navigate to:
http://127.0.0.1:5000
app.py — Core Flask backend routing, security hashing, database initializations, and API integration setups.
templates/home.html — Clean interface viewport layout mapping both the empty grid home state and active book search states.
static/ — Location handling custom web styles, media stylesheets, and user-uploaded asset bundles.
