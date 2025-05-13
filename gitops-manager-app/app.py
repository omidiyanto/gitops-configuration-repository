import os
import shutil
import yaml
import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__)
app.config['DATABASE'] = 'uat_apps.db'

# Initialize database
def init_db():
    # Remove existing database file if it exists (OPTIONAL)
    if os.path.exists(app.config['DATABASE']):
        os.remove(app.config['DATABASE'])
        print(f"Removed existing database: {app.config['DATABASE']}")
    
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL UNIQUE,
            repo_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Created fresh database")

# Get DB connection
def get_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

# Initialize the database (fresh start every time)
init_db()

# Paths - Updated for new location
APPS_DIR = os.path.abspath('../apps')
APPSET_FILE = os.path.abspath('../applicationsets/multiple-app-uat.yaml')
EXAMPLE_APP_DIR = os.path.join(APPS_DIR, 'EXAMPLE_APP')

# Sync database with existing applications
def sync_db_with_existing_apps():
    try:
        # Load applications from YAML file
        with open(APPSET_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        elements = config['spec']['generators'][0]['matrix']['generators'][0]['list']['elements']
        
        conn = get_db()
        for element in elements:
            app_name = element.get('app')
            repo_name = element.get('repo')
            
            # Skip EXAMPLE_APP app
            if app_name == 'EXAMPLE_APP':
                continue
                
            # Check if app already exists in database
            exists = conn.execute('SELECT 1 FROM applications WHERE app_name = ?', 
                              (app_name,)).fetchone()
            
            if not exists and os.path.exists(os.path.join(APPS_DIR, app_name)):
                # Add to database if it exists in filesystem but not in DB
                conn.execute('INSERT INTO applications (app_name, repo_name) VALUES (?, ?)',
                         (app_name, repo_name))
                print(f"Synced app {app_name} to database")
        
        conn.commit()
        conn.close()
        print("Database sync completed")
    except Exception as e:
        print(f"Error syncing database: {str(e)}")

# Call the sync function after fresh database initialization
sync_db_with_existing_apps()

@app.route('/')
def index():
    conn = get_db()
    apps = conn.execute('SELECT * FROM applications ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('index.html', apps=apps)

@app.route('/api/apps', methods=['GET'])
def get_apps():
    conn = get_db()
    apps = conn.execute('SELECT * FROM applications ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(app) for app in apps])

@app.route('/api/apps', methods=['POST'])
def create_app():
    data = request.json
    app_name = data.get('app_name')
    
    if not app_name:
        return jsonify({'success': False, 'message': 'Application name is required'}), 400
    
    # Always use app_name as repo_name
    repo_name = app_name
    
    try:
        # Add to database
        conn = get_db()
        conn.execute('INSERT INTO applications (app_name, repo_name) VALUES (?, ?)',
                     (app_name, repo_name))
        conn.commit()
        
        # Update the multiple-app-uat.yaml file
        update_appset_file(app_name, repo_name, 'add')
        
        # Create app directory structure
        create_app_directory(app_name, repo_name)
        
        conn.close()
        return jsonify({'success': True, 'message': 'Application added successfully'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Application already exists'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/apps/<int:app_id>', methods=['DELETE'])
def delete_app(app_id):
    try:
        conn = get_db()
        app = conn.execute('SELECT * FROM applications WHERE id = ?', (app_id,)).fetchone()
        
        if not app:
            return jsonify({'success': False, 'message': 'Application not found'}), 404
        
        # Delete from YAML file
        update_appset_file(app['app_name'], app['repo_name'], 'delete')
        
        # Delete app directory
        app_dir = os.path.join(APPS_DIR, app['app_name'])
        if os.path.exists(app_dir):
            shutil.rmtree(app_dir)
        
        # Delete from database
        conn.execute('DELETE FROM applications WHERE id = ?', (app_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Application deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/apps/<int:app_id>', methods=['PUT'])
def update_app(app_id):
    data = request.json
    new_app_name = data.get('app_name')
    
    if not new_app_name:
        return jsonify({'success': False, 'message': 'Application name is required'}), 400
    
    # Always use app_name as repo_name
    new_repo_name = new_app_name
     
    try:
        conn = get_db()
        old_app = conn.execute('SELECT * FROM applications WHERE id = ?', (app_id,)).fetchone()
        
        if not old_app:
            return jsonify({'success': False, 'message': 'Application not found'}), 404
        
        # Update YAML file
        update_appset_file(old_app['app_name'], old_app['repo_name'], 'delete')
        update_appset_file(new_app_name, new_repo_name, 'add')
        
        # Update directory if name changed
        if old_app['app_name'] != new_app_name:
            old_dir = os.path.join(APPS_DIR, old_app['app_name'])
            new_dir = os.path.join(APPS_DIR, new_app_name)
            if os.path.exists(old_dir):
                shutil.move(old_dir, new_dir)
                # Update chart name in Chart.yaml
                update_chart_name(new_dir, new_app_name)
        
        # Update database
        conn.execute('UPDATE applications SET app_name = ?, repo_name = ? WHERE id = ?',
                     (new_app_name, new_repo_name, app_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Application updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def update_appset_file(app_name, repo_name, action):
    # Load current configuration
    with open(APPSET_FILE, 'r') as f:
        config = yaml.safe_load(f)
    
    elements = config['spec']['generators'][0]['matrix']['generators'][0]['list']['elements']
    
    # Ensure pullRequest.github.repo is set
    pull_request_generator = config['spec']['generators'][0]['matrix']['generators'][1]['pullRequest']
    if 'github' in pull_request_generator:
        pull_request_generator['github']['repo'] = '{{ .repo }}'
    
    if action == 'add':
        # Check if app already exists
        for element in elements:
            if element.get('app') == app_name:
                return  # Already exists
        
        # Add new app
        elements.append({
            'app': app_name,
            'repo': app_name  # Always use app_name as repo_name
        })
    elif action == 'delete':
        # Remove app
        config['spec']['generators'][0]['matrix']['generators'][0]['list']['elements'] = [
            element for element in elements if element.get('app') != app_name
        ]
    
    # Save updated configuration
    with open(APPSET_FILE, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

def create_app_directory(app_name, repo_name):
    # Create app directory structure based on EXAMPLE_APP
    app_dir = os.path.join(APPS_DIR, app_name)
    
    # Create uat directory
    uat_dir = os.path.join(app_dir, 'uat')
    os.makedirs(os.path.join(uat_dir, 'templates'), exist_ok=True)
    
    # Copy and modify Chart.yaml
    with open(os.path.join(EXAMPLE_APP_DIR, 'uat', 'Chart.yaml'), 'r') as f:
        chart_yaml = yaml.safe_load(f)
    
    chart_yaml['name'] = app_name
    chart_yaml['description'] = f"A Helm chart for {app_name}"
    
    with open(os.path.join(uat_dir, 'Chart.yaml'), 'w') as f:
        yaml.dump(chart_yaml, f, default_flow_style=False)
    
    # Copy and modify values.yaml
    with open(os.path.join(EXAMPLE_APP_DIR, 'uat', 'values.yaml'), 'r') as f:
        values_yaml = yaml.safe_load(f)
    
    values_yaml['image']['repository'] = f"omidiyanto/{app_name}"  # Use app_name instead of repo_name
    
    with open(os.path.join(uat_dir, 'values.yaml'), 'w') as f:
        yaml.dump(values_yaml, f, default_flow_style=False)
    
    # Copy template files
    template_files = ['namespace.yaml', 'service.yaml', 'deployment.yaml']
    for file in template_files:
        shutil.copy(
            os.path.join(EXAMPLE_APP_DIR, 'uat', 'templates', file),
            os.path.join(uat_dir, 'templates', file)
        )

def update_chart_name(app_dir, new_name):
    chart_file = os.path.join(app_dir, 'uat', 'Chart.yaml')
    if os.path.exists(chart_file):
        with open(chart_file, 'r') as f:
            chart_yaml = yaml.safe_load(f)
        
        chart_yaml['name'] = new_name
        
        with open(chart_file, 'w') as f:
            yaml.dump(chart_yaml, f, default_flow_style=False)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 