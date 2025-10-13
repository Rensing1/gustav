#!/usr/bin/env python3
"""
AMD GPU VRAM Monitoring für Vision-Processing Debugging

Nutzt rocm-smi für AMD GPU-Statistiken
"""

import subprocess
import json
import time
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def get_amd_gpu_stats() -> Optional[Dict]:
    """
    Holt AMD GPU VRAM und Auslastung via rocm-smi.
    Fallback auf /sys/class/drm für Basic-Stats.
    """
    try:
        # Primary: rocm-smi (detaillierte Stats)
        result = subprocess.run([
            'rocm-smi', '--showmeminfo', 'vram', '--json'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            gpu_stats = {}
            
            for gpu_id, gpu_data in data.items():
                if 'VRAM Total Memory (B)' in gpu_data and 'VRAM Total Used Memory (B)' in gpu_data:
                    total_bytes = gpu_data['VRAM Total Memory (B)']
                    used_bytes = gpu_data['VRAM Total Used Memory (B)']
                    
                    gpu_stats[gpu_id] = {
                        'vram_total_mb': round(total_bytes / (1024**2)),
                        'vram_used_mb': round(used_bytes / (1024**2)),
                        'vram_free_mb': round((total_bytes - used_bytes) / (1024**2)),
                        'vram_usage_percent': round((used_bytes / total_bytes) * 100, 1),
                        'timestamp': datetime.now().isoformat()
                    }
            
            return gpu_stats
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        pass
    
    try:
        # Fallback: /sys/class/drm (Basic Memory Info)
        with open('/sys/class/drm/card0/device/mem_info_vram_used', 'r') as f:
            used_bytes = int(f.read().strip())
        with open('/sys/class/drm/card0/device/mem_info_vram_total', 'r') as f:
            total_bytes = int(f.read().strip())
            
        return {
            'card0': {
                'vram_total_mb': round(total_bytes / (1024**2)),
                'vram_used_mb': round(used_bytes / (1024**2)),
                'vram_free_mb': round((total_bytes - used_bytes) / (1024**2)),
                'vram_usage_percent': round((used_bytes / total_bytes) * 100, 1),
                'timestamp': datetime.now().isoformat(),
                'method': 'sysfs_fallback'
            }
        }
    except (FileNotFoundError, ValueError):
        pass
    
    # Ultimate Fallback: Docker stats für Container-Memory
    try:
        result = subprocess.run([
            'docker', 'stats', 'gustav_ollama', '--no-stream', '--format', 
            'table {{.MemUsage}}\t{{.MemPerc}}'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:  # Header + data
                mem_usage, mem_perc = lines[1].split('\t')
                return {
                    'ollama_container': {
                        'container_memory': mem_usage.strip(),
                        'container_memory_percent': mem_perc.strip(),
                        'timestamp': datetime.now().isoformat(),
                        'method': 'docker_fallback'
                    }
                }
    except:
        pass
    
    return None

def log_gpu_stats_during_vision():
    """
    Kontinuierliches GPU-Monitoring während Vision-Processing.
    Für manuelle Aufrufe während Tests.
    """
    print("🔍 AMD GPU Monitoring gestartet (Ctrl+C zum Beenden)")
    print("📊 Format: [TIMESTAMP] VRAM: used/total (usage%)")
    print("-" * 60)
    
    try:
        while True:
            stats = get_amd_gpu_stats()
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            if stats:
                for gpu_id, data in stats.items():
                    used = data['vram_used_mb']
                    total = data['vram_total_mb']
                    usage = data['vram_usage_percent']
                    method = data.get('method', 'rocm-smi')
                    
                    print(f"[{timestamp}] GPU {gpu_id}: {used}MB/{total}MB ({usage}%) [{method}]")
            else:
                print(f"[{timestamp}] ⚠️ GPU Stats nicht verfügbar")
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n✅ GPU Monitoring beendet")

if __name__ == "__main__":
    log_gpu_stats_during_vision()