import cv2
import numpy as np
import threading
import time
import json
import os
import argparse
from flask import Flask, Response, render_template_string

# Configuration
tile_width = 360  # 16:9 aspect ratio
tile_height = 200  # 16:9 aspect ratio (640/360 = 16/9)
frame_update_interval = 0.133  # ~30 FPS display update rate

# Load configuration from JSON file
config_file = 'config.json'
if os.path.exists(config_file):
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        rows = config.get('rows', 2)
        cols = config.get('cols', 2)
        rtsp_urls = config.get('rtsp_urls', [])
        print(f"Loaded configuration: {rows}x{cols} grid, {len(rtsp_urls)} RTSP URLs from {config_file}")
    except Exception as e:
        print(f"Error loading {config_file}: {e}")
        print("Using default configuration")
        rows = 2
        cols = 2
        rtsp_urls = []
else:
    print(f"Configuration file {config_file} not found, using default configuration")
    rows = 2
    cols = 2
    rtsp_urls = []

num_tiles = rows * cols

# Ensure we have enough URLs, pad with empty
while len(rtsp_urls) < num_tiles:
    rtsp_urls.append("")

rtsp_urls = rtsp_urls[:num_tiles]

# Shared list for frames with locks
frames = [None] * num_tiles
frame_locks = [threading.Lock() for _ in range(num_tiles)]
captures = [None] * num_tiles
running = True
capture_threads = []

# Cached blank frames to reduce RAM allocation
connecting_frame = None
no_stream_frame = None
grid = None

def create_blank_frame(text, color=(255, 255, 255)):
    """Create a blank frame with text"""
    blank = np.zeros((tile_height, tile_width, 3), dtype=np.uint8)
    cv2.putText(blank, text, (50, tile_height//2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return blank

def resize_with_aspect_ratio(frame, target_width, target_height):
    """Resize frame maintaining aspect ratio and add letterboxing/pillarboxing"""
    h, w = frame.shape[:2]
    target_aspect = target_width / target_height
    frame_aspect = w / h
    
    if frame_aspect > target_aspect:
        # Frame is wider - fit to width, add letterboxing
        new_width = target_width
        new_height = int(target_width / frame_aspect)
        resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        
        # Create output with black borders
        output = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        y_offset = (target_height - new_height) // 2
        output[y_offset:y_offset + new_height, :] = resized
    else:
        # Frame is taller - fit to height, add pillarboxing
        new_height = target_height
        new_width = int(target_height * frame_aspect)
        resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        
        # Create output with black borders
        output = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        x_offset = (target_width - new_width) // 2
        output[:, x_offset:x_offset + new_width] = resized
    
    return output

def setup_rtsp_capture(url):
    """Setup VideoCapture with RTSP-optimized settings"""
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    
    # RTSP-specific options to prevent hanging
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer to get latest frame
    cap.set(cv2.CAP_PROP_FPS, 5)
    
    # Try to set additional options for better RTSP handling
    try:
        # These may not work on all backends, but won't hurt
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
    except:
        pass
    
    return cap

def capture_stream(url, index):
    """Continuously capture frames from RTSP stream"""
    global no_stream_frame
    if not url.strip():
        with frame_locks[index]:
            frames[index] = no_stream_frame
        return
    
    reconnect_delay = 2.0
    max_reconnect_delay = 30.0
    consecutive_errors = 0
    
    while running:
        cap = None
        try:
            # Setup capture with timeout handling
            cap = setup_rtsp_capture(url)
            
            if not cap.isOpened():
                raise Exception("Failed to open stream")
            
            consecutive_errors = 0
            reconnect_delay = 2.0  # Reset delay on success
            
            # Read frames continuously
            while running:
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    # Resize frame maintaining aspect ratio
                    frame = resize_with_aspect_ratio(frame, tile_width, tile_height)
                    
                    # Update shared frame with lock
                    with frame_locks[index]:
                        frames[index] = frame
                    
                    consecutive_errors = 0
                else:
                    # Frame read failed, try to reconnect
                    consecutive_errors += 1
                    if consecutive_errors > 10:
                        raise Exception("Multiple read failures")
                    time.sleep(0.1)
                
                # Small delay to prevent CPU spinning
                time.sleep(0.01)
                
        except Exception as e:
            # Error occurred, show error frame
            error_text = f"Error: {str(e)[:15]}"
            with frame_locks[index]:
                frames[index] = create_blank_frame(error_text, (0, 0, 255))
            
            consecutive_errors += 1
            
            # Exponential backoff for reconnection
            if running:
                time.sleep(min(reconnect_delay, max_reconnect_delay))
                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
        
        finally:
            # Clean up capture
            if cap is not None:
                try:
                    cap.release()
                except:
                    pass

def initialize_application():
    """Initialize frames and start capture threads"""
    global frames, frame_locks, capture_threads, running, num_tiles, rtsp_urls, rows, cols, connecting_frame, no_stream_frame, grid
    
    # Recalculate num_tiles based on current config
    num_tiles = rows * cols
    
    # Create cached blank frames
    connecting_frame = create_blank_frame("Connecting...", (255, 255, 0))
    no_stream_frame = create_blank_frame("No Stream", (128, 128, 128))
    
    # Create the grid
    grid_height = rows * tile_height
    grid_width = cols * tile_width
    grid = np.zeros((grid_height, grid_width, 3), dtype=np.uint8)
    
    # Create a local copy of rtsp_urls and pad if needed
    rtsp_urls_local = list(rtsp_urls)
    while len(rtsp_urls_local) < num_tiles:
        rtsp_urls_local.append("")
    
    rtsp_urls_local = rtsp_urls_local[:num_tiles]
    
    # Initialize frames and locks
    frames = [None] * num_tiles
    frame_locks = [threading.Lock() for _ in range(num_tiles)]
    
    # Initialize frames with connecting message
    for i in range(num_tiles):
        frames[i] = connecting_frame
    
    # Start capture threads (daemon threads so they exit when main exits)
    capture_threads = []
    running = True
    for i, url in enumerate(rtsp_urls_local):
        t = threading.Thread(target=capture_stream, args=(url, i), daemon=True)
        t.start()
        capture_threads.append(t)
    
    # Give threads a moment to start
    time.sleep(1)

def stop_application():
    """Stop all capture threads and clean up"""
    global running, capture_threads
    
    # Signal threads to stop
    running = False
    
    # Wait for threads to finish
    if capture_threads:
        for thread in capture_threads:
            thread.join(timeout=1.0)
    
    capture_threads = []
    time.sleep(0.5)

def restart_application():
    """Restart the application with current configuration"""
    global rtsp_urls, rows, cols
    print("\nRestarting application with new configuration...")
    
    # Reload configuration from JSON file
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            rows = config.get('rows', rows)
            cols = config.get('cols', cols)
            rtsp_urls = config.get('rtsp_urls', [])
            print(f"Reloaded configuration: {rows}x{cols} grid, {len(rtsp_urls)} RTSP URLs from {config_file}")
        except Exception as e:
            print(f"Error reloading {config_file}: {e}")
            print("Keeping current configuration")
    
    stop_application()
    initialize_application()
    print("Application restarted successfully!")

def update_grid():
    """Update the grid with current frames"""
    global grid
    for i in range(rows):
        for j in range(cols):
            idx = i * cols + j
            y_start = i * tile_height
            y_end = (i + 1) * tile_height
            x_start = j * tile_width
            x_end = (j + 1) * tile_width
            
            with frame_locks[idx]:
                if frames[idx] is not None:
                    grid[y_start:y_end, x_start:x_end] = frames[idx]

def run_windows_app():
    """Run the application as a Windows desktop application"""
    print("CCTV Multi-Stream Viewer Started (Windows App Mode)")
    print("Press 'q' to quit, 'R' to restart with new configuration")
    
    try:
        # Main display loop
        while True:
            update_grid()
            
            # Display the grid
            cv2.imshow('CCTV Multi-Stream', grid)
            
            # Make window always on top
            cv2.setWindowProperty('CCTV Multi-Stream', cv2.WND_PROP_TOPMOST, 1)
            
            # Handle key presses
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r') or key == ord('R'):
                restart_application()
            
            # Control frame rate
            time.sleep(frame_update_interval)
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    
    finally:
        # Stop all threads and clean up
        stop_application()
        cv2.destroyAllWindows()
        print("Cleanup complete")

def run_web_app(host='0.0.0.0', port=5000):
    """Run the application as a Flask web server"""
    app = Flask(__name__)
    
    # HTML template for the web interface
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CCTV Multi-Stream Viewer</title>
        <style>
            body {
                margin: 0;
                padding: 20px;
                background-color: #1a1a1a;
                color: #ffffff;
                font-family: Arial, sans-serif;
            }
            h1 {
                text-align: center;
                margin-bottom: 20px;
            }
            #stream-container {
                display: flex;
                justify-content: center;
                align-items: center;
                width: 100%;
            }
            #stream {
                max-width: 100%;
                height: auto;
                border: 2px solid #333;
                box-shadow: 0 4px 8px rgba(0,0,0,0.5);
            }
            .info {
                text-align: center;
                margin-top: 20px;
                color: #888;
            }
        </style>
    </head>
    <body>
        <h1>CCTV Multi-Stream Viewer</h1>
        <div id="stream-container">
            <img id="stream" src="/video_feed" alt="Video Stream">
        </div>
        <div class="info">
            <p>Grid: {{ rows }}x{{ cols }} | Streams: {{ num_streams }}</p>
            <p>Refresh this page to restart with new configuration</p>
        </div>
        <script>
            // MJPEG stream handles updates automatically, no refresh needed
        </script>
    </body>
    </html>
    """
    
    def generate_frames():
        """Generator function for video streaming"""
        while running:
            update_grid()
            
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                continue
            
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            
            time.sleep(frame_update_interval)
    
    @app.route('/')
    def index():
        """Main page"""
        num_streams = sum(1 for url in rtsp_urls if url.strip())
        return render_template_string(html_template, rows=rows, cols=cols, num_streams=num_streams)
    
    @app.route('/video_feed')
    def video_feed():
        """Video streaming route"""
        return Response(generate_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    
    print(f"CCTV Multi-Stream Viewer Started (Web Mode)")
    print(f"Open your browser and navigate to: http://localhost:{port}")
    print(f"Or access from other devices: http://<your-ip>:{port}")
    print("Press Ctrl+C to stop")
    
    try:
        app.run(host=host, port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_application()
        print("Cleanup complete")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='CCTV Multi-Stream Viewer')
    parser.add_argument('--mode', choices=['windows', 'web'], default='windows',
                        help='Application mode: windows (desktop app) or web (Flask server)')
    parser.add_argument('--host', default='0.0.0.0',
                        help='Host for web mode (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000,
                        help='Port for web mode (default: 5000)')
    
    args = parser.parse_args()
    
    # Initialize application
    initialize_application()
    
    # Run in selected mode
    if args.mode == 'web':
        run_web_app(host=args.host, port=args.port)
    else:
        run_windows_app()

if __name__ == '__main__':
    main()
