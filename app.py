from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import requests
import time
from datetime import datetime
import threading
import os

app = Flask(__name__)
CORS(app)

DB_NAME = 'iss_data.db'

# Database initialization
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS iss_telemetry
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp INTEGER,
                  latitude REAL,
                  longitude REAL,
                  altitude REAL,
                  velocity REAL,
                  visibility TEXT,
                  footprint REAL,
                  daynum REAL,
                  solar_lat REAL,
                  solar_lon REAL,
                  units TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# Background ISS data fetch
def fetch_and_store_iss_data():
    while True:
        try:
            resp = requests.get('https://api.wheretheiss.at/v1/satellites/25544', timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute('''INSERT INTO iss_telemetry 
                            (timestamp, latitude, longitude, altitude, velocity, visibility,
                             footprint, daynum, solar_lat, solar_lon, units)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (data['timestamp'], data['latitude'], data['longitude'], data['altitude'],
                           data['velocity'], data['visibility'], data['footprint'], data['daynum'],
                           data['solar_lat'], data['solar_lon'], data['units']))
                conn.commit()
                conn.close()
            time.sleep(60)
        except Exception as e:
            print(f"Error fetching ISS data: {e}")
            time.sleep(60)

# Routes
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/data')
def data_page():
    return send_from_directory('.', 'data.html')

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/current')
def current():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM iss_telemetry ORDER BY created_at DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({
            "id": row[0], "timestamp": row[1], "latitude": row[2], "longitude": row[3],
            "altitude": row[4], "velocity": row[5], "visibility": row[6], "footprint": row[7],
            "daynum": row[8], "solar_lat": row[9], "solar_lon": row[10], "units": row[11],
            "created_at": row[12]
        })
    return jsonify({"error": "No data"}), 404

@app.route('/history')
def history():
    limit = min(request.args.get('limit', 500, type=int), 10000)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM iss_telemetry ORDER BY created_at DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return jsonify({"count": len(rows), "data": [
        {"id": r[0], "timestamp": r[1], "latitude": r[2], "longitude": r[3], 
         "altitude": r[4], "velocity": r[5], "visibility": r[6], "footprint": r[7],
         "daynum": r[8], "solar_lat": r[9], "solar_lon": r[10], "units": r[11],
         "created_at": r[12]} for r in rows
    ]})

# Initialize DB and start background thread
if __name__ == '__main__':
    init_db()
    threading.Thread(target=fetch_and_store_iss_data, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
