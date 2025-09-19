import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
import os

class NetworkLogger:
    def __init__(self, db_path: str = "../logs/network_logs.db"):
        self.db_path = db_path
        # Buat direktori logs jika belum ada
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """
        Inisialisasi database SQLite dengan tabel untuk ping dan traceroute
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tabel untuk log ping
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ping_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    host TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    packets_sent INTEGER,
                    packets_received INTEGER,
                    packet_loss INTEGER,
                    packet_loss_percent REAL,
                    min_time_ms REAL,
                    max_time_ms REAL,
                    avg_time_ms REAL,
                    error_message TEXT,
                    raw_output TEXT,
                    command TEXT
                )
            ''')
            
            # Tabel untuk log traceroute
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS traceroute_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    host TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    total_hops INTEGER,
                    hops_data TEXT,  -- JSON string berisi hop details
                    error_message TEXT,
                    raw_output TEXT,
                    command TEXT
                )
            ''')
            
            # Index untuk performa query
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ping_timestamp ON ping_logs(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ping_host ON ping_logs(host)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trace_timestamp ON traceroute_logs(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trace_host ON traceroute_logs(host)')
            
            conn.commit()
    
    def log_ping_result(self, ping_result: Dict) -> int:
        """
        Simpan hasil ping ke database
        Returns: ID record yang baru disimpan
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO ping_logs (
                    timestamp, host, success, packets_sent, packets_received,
                    packet_loss, packet_loss_percent, min_time_ms, max_time_ms,
                    avg_time_ms, error_message, raw_output, command
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ping_result.get('timestamp', datetime.now().isoformat()),
                ping_result.get('host', ''),
                ping_result.get('success', False),
                ping_result.get('packets_sent'),
                ping_result.get('packets_received'),
                ping_result.get('packet_loss'),
                ping_result.get('packet_loss_percent'),
                ping_result.get('min_time_ms'),
                ping_result.get('max_time_ms'),
                ping_result.get('avg_time_ms'),
                ping_result.get('error'),
                ping_result.get('raw_output'),
                ping_result.get('command')
            ))
            
            record_id = cursor.lastrowid
            conn.commit()
            return record_id
    
    def log_traceroute_result(self, trace_result: Dict) -> int:
        """
        Simpan hasil traceroute ke database
        Returns: ID record yang baru disimpan
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Convert hops data ke JSON string
            hops_json = json.dumps(trace_result.get('hops', []))
            
            cursor.execute('''
                INSERT INTO traceroute_logs (
                    timestamp, host, success, total_hops, hops_data,
                    error_message, raw_output, command
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trace_result.get('timestamp', datetime.now().isoformat()),
                trace_result.get('host', ''),
                trace_result.get('success', False),
                trace_result.get('total_hops'),
                hops_json,
                trace_result.get('error'),
                trace_result.get('raw_output'),
                trace_result.get('command')
            ))
            
            record_id = cursor.lastrowid
            conn.commit()
            return record_id
    
    def get_ping_history(self, host: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Ambil history ping dari database
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if host:
                cursor.execute('''
                    SELECT * FROM ping_logs 
                    WHERE host = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (host, limit))
            else:
                cursor.execute('''
                    SELECT * FROM ping_logs 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
            
            columns = [description[0] for description in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                results.append(result)
            
            return results
    
    def get_traceroute_history(self, host: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Ambil history traceroute dari database
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if host:
                cursor.execute('''
                    SELECT * FROM traceroute_logs 
                    WHERE host = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (host, limit))
            else:
                cursor.execute('''
                    SELECT * FROM traceroute_logs 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
            
            columns = [description[0] for description in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                # Parse hops data dari JSON
                if result['hops_data']:
                    try:
                        result['hops'] = json.loads(result['hops_data'])
                    except json.JSONDecodeError:
                        result['hops'] = []
                del result['hops_data']  # Remove raw JSON field
                results.append(result)
            
            return results
    
    def get_statistics(self) -> Dict:
        """
        Ambil statistik umum dari database
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Ping statistics
            cursor.execute('SELECT COUNT(*) FROM ping_logs')
            total_pings = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM ping_logs WHERE success = 1')
            successful_pings = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT host) FROM ping_logs')
            unique_ping_hosts = cursor.fetchone()[0]
            
            # Traceroute statistics
            cursor.execute('SELECT COUNT(*) FROM traceroute_logs')
            total_traces = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM traceroute_logs WHERE success = 1')
            successful_traces = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT host) FROM traceroute_logs')
            unique_trace_hosts = cursor.fetchone()[0]
            
            # Recent activity
            cursor.execute('''
                SELECT host, COUNT(*) as count 
                FROM ping_logs 
                WHERE timestamp > datetime('now', '-1 day')
                GROUP BY host 
                ORDER BY count DESC 
                LIMIT 5
            ''')
            recent_ping_hosts = cursor.fetchall()
            
            return {
                'ping_stats': {
                    'total_tests': total_pings,
                    'successful_tests': successful_pings,
                    'success_rate': (successful_pings / total_pings * 100) if total_pings > 0 else 0,
                    'unique_hosts': unique_ping_hosts
                },
                'traceroute_stats': {
                    'total_tests': total_traces,
                    'successful_tests': successful_traces,
                    'success_rate': (successful_traces / total_traces * 100) if total_traces > 0 else 0,
                    'unique_hosts': unique_trace_hosts
                },
                'recent_activity': {
                    'top_ping_hosts_24h': [{'host': host, 'count': count} for host, count in recent_ping_hosts]
                }
            }
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """
        Hapus log lama untuk menghemat space
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cutoff_date = datetime.now().isoformat()
            
            cursor.execute('''
                DELETE FROM ping_logs 
                WHERE timestamp < datetime('now', '-{} days')
            '''.format(days_to_keep))
            
            cursor.execute('''
                DELETE FROM traceroute_logs 
                WHERE timestamp < datetime('now', '-{} days')
            '''.format(days_to_keep))
            
            deleted_ping = cursor.rowcount
            conn.commit()
            
            return {
                'deleted_records': deleted_ping,
                'cutoff_date': cutoff_date
            }

# Test function
if __name__ == "__main__":
    logger = NetworkLogger()
    
    # Test ping log
    test_ping = {
        'success': True,
        'host': 'google.com',
        'packets_sent': 4,
        'packets_received': 4,
        'packet_loss': 0,
        'packet_loss_percent': 0.0,
        'min_time_ms': 10.5,
        'max_time_ms': 15.2,
        'avg_time_ms': 12.8,
        'timestamp': datetime.now().isoformat(),
        'command': 'ping -n 4 google.com',
        'raw_output': 'Pinging google.com...'
    }
    
    ping_id = logger.log_ping_result(test_ping)
    print(f"Ping logged with ID: {ping_id}")
    
    # Test traceroute log
    test_trace = {
        'success': True,
        'host': 'google.com',
        'total_hops': 3,
        'hops': [
            {'hop': 1, 'hostname': '192.168.1.1', 'times': ['1 ms', '1 ms', '2 ms']},
            {'hop': 2, 'hostname': '10.0.0.1', 'times': ['5 ms', '6 ms', '5 ms']},
            {'hop': 3, 'hostname': 'google.com', 'times': ['15 ms', '16 ms', '14 ms']}
        ],
        'timestamp': datetime.now().isoformat(),
        'command': 'tracert google.com',
        'raw_output': 'Tracing route to google.com...'
    }
    
    trace_id = logger.log_traceroute_result(test_trace)
    print(f"Traceroute logged with ID: {trace_id}")
    
    # Test statistics
    stats = logger.get_statistics()
    print("\nStatistics:")
    print(json.dumps(stats, indent=2))
    
    # Test history
    ping_history = logger.get_ping_history(limit=5)
    print(f"\nFound {len(ping_history)} ping records")
    
    trace_history = logger.get_traceroute_history(limit=5)
    print(f"Found {len(trace_history)} traceroute records")