# EMPATH — AI-Assisted Hospital Monitoring System

EMPATH is an AI-assisted hospital monitoring and patient-safety project designed to support hospital staff through video-based activity analysis, potential fall detection, alerts, and role-based monitoring workflows.

The project combines a React frontend with a Python backend and computer-vision components to help organize monitoring information and alert-management workflows.

> **Disclaimer:** EMPATH is a software prototype, not a certified medical device. Its detections may produce false positives or false negatives. It must not replace clinical judgement, direct patient supervision, or established hospital emergency procedures.

## Key Features

- **Live Video Monitoring:** Monitor live camera feeds and analyze video frames.
- **Potential Fall Detection:** Identify activity patterns that may indicate a possible fall and support alert generation.
- **Bed Movement Analysis:** Analyze movement patterns using the project's computer-vision components.
- **Alert Management:** View and manage alerts through the monitoring interface.
- **Alert Handoff:** Support alert assignment and handoff workflows between authorized staff.
- **Alert History and Auditing:** Maintain alert-related workflow information, including dismissal and handoff records.
- **Multi-Camera Dashboard:** Organize monitoring across multiple cameras.
- **Video Playback and Event Review:** Review available video and event information.
- **Role-Based Access Control:** Separate access for Admin, Nurse, Doctor, and Researcher roles.
- **User and Camera Management:** Provide interfaces for managing users, cameras, and hospital structure.
- **Automated Tests:** Include backend tests for APIs, permissions, security, and alert workflows.

## Technology Stack

### Frontend
- React
- Vite
- JavaScript
- CSS

### Backend
- Python
- FastAPI
- SQLAlchemy
- Alembic
- SQLite-based local development database configuration

### Computer Vision and Analysis
- OpenCV
- MediaPipe-based pose analysis
- Custom behavior and bed-movement analysis modules

### Testing and Development
- pytest
- Git and GitHub
- Node.js and npm

## Project Structure

```text
EMPATH/
├── backend/
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── ai/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   ├── scripts/
│   ├── tests/
│   └── pytest.ini
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   └── pages/
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Prerequisites

Install the following before running the project:

- Python 3.10.x
- Node.js and npm
- Git
- A webcam or compatible video source for live-monitoring features

Some features may require additional system configuration or model assets.

## Setup and Installation

The commands below are intended for Windows Command Prompt. Run the backend and frontend in separate terminals.

### 1. Clone the Repository

```cmd
git clone https://github.com/Piyush954853/EMPATH.git
cd EMPATH
```

If the repository's default branch is not configured for your checkout, select the intended branch before continuing.

### 2. Create and Activate the Python Environment

From the project root:

```cmd
py -3.10 -m venv .venv
.venv\Scripts\activate
```

### 3. Install Backend Dependencies

```cmd
cd backend
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configure the database and any required environment variables according to the project's active configuration. Never commit real passwords, API keys, tokens, or patient data.

For initial administrator creation through the seed script, `EMPATH_ADMIN_INITIAL_PASSWORD` must be configured with a strong password if that requirement is enabled in your local version of the script.

### 4. Apply Database Migrations

From the `backend` directory, run:

```cmd
python -m alembic upgrade head
```

Confirm that the database configuration is correct before applying migrations to an existing database.

### 5. Start the Backend

From the `backend` directory:

```cmd
uvicorn app.main:app --reload
```

The local backend is expected to run at:

`http://127.0.0.1:8000`

The API documentation is available at `/docs` when enabled by the running application.

### 6. Install and Start the Frontend

Open a second terminal:

```cmd
cd /d "C:\Users\Piyush\Desktop\empath\frontend"
npm ci
npm run dev
```

Open the local development URL printed by Vite, typically:

`http://localhost:5173`

The frontend's API configuration must point to the running backend.

## Testing

### Backend Tests

Activate the project's Python environment, navigate to `backend`, and run:

```cmd
python -m pytest -q
```

At the checkpoint documented for this repository, **61 backend tests passed**.

### Frontend Production Build

From the `frontend` directory:

```cmd
npm run build
```

The production build was successful at the same checkpoint.

These results describe the tests and build run at that point in development; they do not establish clinical accuracy or guarantee that every deployment configuration works.

## Security Notes

- Use strong, unique passwords for administrator accounts.
- Supply credentials through secure environment variables or an appropriate secrets manager.
- Never commit `.env` files, credentials, database files containing real data, or private patient information.
- Restrict access according to each user's role.
- Keep dependencies updated and review security alerts before publishing or deploying.
- Treat video footage and monitoring data as sensitive information.
- Keep the repository private until the security review and historical credential cleanup are complete.

## Current Project Status

The frontend production build and backend test suite passed at the recorded development checkpoint. The system's monitoring and alert workflows are under active development and require continued integration, security, and real-world scenario testing.

## Limitations

EMPATH is an educational and development project. Fall-detection performance depends on video quality, camera placement, body visibility, and movement patterns. The system has not been established as a clinically validated fall-prevention or emergency-response solution.

## License

A license has not yet been specified. Until a license is added, do not assume that the source code may be reused or redistributed.