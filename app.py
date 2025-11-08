from flask import Flask, jsonify, request, send_file
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

# --- Database setup ---
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

# --- Background ISS data fetch ---
def fetch_and_store_iss_data():
    while True:
        try:
            response = requests.get('https://api.wheretheiss.at/v1/satellites/25544', timeout=10)
            if response.status_code == 200:
                data = response.json()
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute('''INSERT INTO iss_telemetry 
                             (timestamp, latitude, longitude, altitude, velocity, 
                              visibility, footprint, daynum, solar_lat, solar_lon, units)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (data['timestamp'], data['latitude'], data['longitude'],
                           data['altitude'], data['velocity'], data['visibility'],
                           data['footprint'], data['daynum'], data['solar_lat'],
                           data['solar_lon'], data['units']))
                conn.commit()
                conn.close()
                print(f"Data stored at {datetime.now()}")
            time.sleep(60)  # fetch every 60 seconds
        except Exception as e:
            print(f"Error fetching data: {e}")
            time.sleep(60)

# --- Serve the dashboard ---
@app.route('/')
def dashboard():
    # Serve your GitHub-hosted index.html
    return send_file('index.html')  # make sure index.html is in the same folder as app.py

# --- Health check ---
@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# --- Current ISS data ---
@app.route('/current')
def get_current():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''SELECT * FROM iss_telemetry 
                     ORDER BY created_at DESC LIMIT 1''')
        row = c.fetchone()
        conn.close()
        
        if row:
            return jsonify({
                "id": row[0],
                "timestamp": row[1],
                "latitude": row[2],
                "longitude": row[3],
                "altitude": row[4],
                "velocity": row[5],
                "visibility": row[6],
                "footprint": row[7],
                "daynum": row[8],
                "solar_lat": row[9],
                "solar_lon": row[10],
                "units": row[11],
                "created_at": row[12]
            })
        else:
            return jsonify({"error": "No data available"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Historical data ---
@app.route('/history')
def get_history():
    try:
        limit = request.args.get('limit', 100, type=int)
        limit = min(limit, 10000)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''SELECT * FROM iss_telemetry ORDER BY created_at DESC LIMIT ?''', (limit,))
        rows = c.fetchall()
        conn.close()
        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "timestamp": row[1],
                "latitude": row[2],
                "longitude": row[3],
                "altitude": row[4],
                "velocity": row[5],
                "visibility": row[6],
                "footprint": row[7],
                "daynum": row[8],
                "solar_lat": row[9],
                "solar_lon": row[10],
                "units": row[11],
                "created_at": row[12]
            })
        return jsonify({"count": len(data), "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Analytics ---
@app.route('/analytics')
def get_analytics():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('SELECT MIN(longitude), MAX(longitude) FROM iss_telemetry')
        lon_data = c.fetchone()
        c.execute('SELECT MIN(altitude), MAX(altitude) FROM iss_telemetry')
        alt_data = c.fetchone()
        c.execute('SELECT altitude FROM iss_telemetry ORDER BY created_at ASC LIMIT 1')
        first_alt = c.fetchone()
        c.execute('SELECT altitude FROM iss_telemetry ORDER BY created_at DESC LIMIT 1')
        last_alt = c.fetchone()
        c.execute('SELECT COUNT(*) FROM iss_telemetry')
        count = c.fetchone()[0]
        c.execute('SELECT MIN(created_at), MAX(created_at) FROM iss_telemetry')
        date_range = c.fetchone()
        conn.close()
        
        altitude_change = 0
        if first_alt and last_alt:
            altitude_change = last_alt[0] - first_alt[0]
        
        return jsonify({
            "total_records": count,
            "date_range": {"start": date_range[0], "end": date_range[1]},
            "longitude": {"min": lon_data[0], "max": lon_data[1]},
            "altitude": {"min": alt_data[0], "max": alt_data[1], "change": altitude_change}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Daily stats ---
@app.route('/stats/daily')
def get_daily_stats():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''SELECT DATE(created_at) as date,
                            COUNT(*) as count,
                            AVG(altitude) as avg_altitude,
                            MIN(altitude) as min_altitude,
                            MAX(altitude) as max_altitude
                     FROM iss_telemetry
                     GROUP BY DATE(created_at)
                     ORDER BY date DESC''')
        rows = c.fetchall()
        conn.close()
        stats = []
        for row in rows:
            stats.append({
                "date": row[0],
                "count": row[1],
                "avg_altitude": row[2],
                "min_altitude": row[3],
                "max_altitude": row[4]
            })
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    # Start data collection thread
    threading.Thread(target=fetch_and_store_iss_data, daemon=True).start()
    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
