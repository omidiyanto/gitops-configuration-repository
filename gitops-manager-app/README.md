# UAT Application Manager

A Flask-based web application for managing UAT (User Acceptance Testing) applications in an Argo CD GitOps environment. This application allows you to create, read, update, and delete UAT applications through a modern, responsive web interface.

## Features

- Create new UAT applications with associated Helm charts
- View existing UAT applications
- Update application configurations
- Delete applications and all associated resources
- Dark mode UI with responsive design
- SQLite database for persistence

## Requirements

- Python 3.8+
- Git
- Access to a Kubernetes cluster with Argo CD

## Installation

1. Clone the repository:

```bash
git clone https://github.com/omidiyanto/gitops-configuration-repository.git
cd gitops-configuration-repository/apps/uat-app-manager
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:

```bash
python app.py
```

2. Open your browser and navigate to:

```
http://localhost:5000
```

## How It Works

The application manages UAT applications by:

1. Reading/writing entries to the Argo CD ApplicationSet configuration (`multiple-app-uat.yaml`)
2. Creating appropriate directory structures and Helm charts for new applications
3. Storing application metadata in a SQLite database
4. Handling updates and deletions of apps and their resources

## Directory Structure

```
uat-app-manager/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates
│   └── index.html      # Main UI template
└── uat_apps.db         # SQLite database (created on first run)
```

## Development

To run the application in development mode with auto-reloading:

```bash
export FLASK_ENV=development
export FLASK_APP=app.py
flask run
``` 