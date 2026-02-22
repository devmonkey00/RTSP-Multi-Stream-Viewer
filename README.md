# RTSP Multi-Stream Viewer

A Python application for viewing multiple RTSP (Real-Time Streaming Protocol) camera streams simultaneously in a grid layout. Supports both Windows desktop application and web-based viewing via Flask.

## Features

- **Multi-Stream Support**: View multiple RTSP camera streams in a customizable grid layout
- **Dual Mode Operation**:
  - **Windows App Mode**: Native desktop application with OpenCV window
  - **Web Mode**: Flask-based web server accessible from any device on your network
- **Automatic Reconnection**: Handles connection failures with exponential backoff retry
- **Aspect Ratio Preservation**: Maintains original video aspect ratios with letterboxing/pillarboxing
- **Configuration File**: Easy setup via JSON configuration file
- **Real-time Updates**: Low-latency streaming with optimized frame buffering
- **Error Handling**: Graceful error handling with visual feedback

## Requirements

- Python 3.7 or higher
- OpenCV (cv2)
- Flask
- NumPy

## Installation

1. Clone or download this repository

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install opencv-python Flask numpy
```

## Configuration

Create a `config.json` file in the project directory with the following structure:

```json
{
  "rows": 2,
  "cols": 2,
  "rtsp_urls": [
    "rtsp://username:password@192.168.1.100:554/stream1",
    "rtsp://username:password@192.168.1.101:554/stream1",
    "rtsp://username:password@192.168.1.102:554/stream1",
    "rtsp://username:password@192.168.1.103:554/stream1"
  ]
}
```

### Configuration Parameters

- **rows**: Number of rows in the grid (default: 2)
- **cols**: Number of columns in the grid (default: 2)
- **rtsp_urls**: Array of RTSP stream URLs. You can use empty strings `""` for unused grid positions

### RTSP URL Format

RTSP URLs typically follow this format:
```
rtsp://[username]:[password]@[ip_address]:[port]/[stream_path]
```

Examples:
- `rtsp://admin:password123@192.168.1.100:554/stream1`
- `rtsp://user:pass@10.0.0.50:8554/live`
- `rtsp://192.168.1.200:554/`

## Usage

### Windows App Mode (Default)

Run as a desktop application with OpenCV window:

```bash
python main.py
```

Or explicitly specify Windows mode:
```bash
python main.py --mode windows
```

**Controls:**
- Press `q` to quit
- Press `R` to restart and reload configuration from `config.json`

### Web Mode

Run as a Flask web server:

```bash
python main.py --mode web
```

**Default Access:**
- Local: `http://localhost:5000`
- Network: `http://<your-ip-address>:5000`

**Custom Port:**
```bash
python main.py --mode web --port 8080
```

**Custom Host and Port:**
```bash
python main.py --mode web --host 0.0.0.0 --port 5000
```

**Command-line Options:**
- `--mode`: Choose `windows` or `web` (default: `windows`)
- `--host`: Host address for web mode (default: `0.0.0.0`)
- `--port`: Port number for web mode (default: `5000`)

## Examples

### Example 1: 2x2 Grid with 4 Cameras

```json
{
  "rows": 2,
  "cols": 2,
  "rtsp_urls": [
    "rtsp://admin:pass@192.168.1.100:554/stream1",
    "rtsp://admin:pass@192.168.1.101:554/stream1",
    "rtsp://admin:pass@192.168.1.102:554/stream1",
    "rtsp://admin:pass@192.168.1.103:554/stream1"
  ]
}
```

### Example 2: 3x3 Grid with 6 Cameras

```json
{
  "rows": 3,
  "cols": 3,
  "rtsp_urls": [
    "rtsp://admin:pass@192.168.1.100:554/stream1",
    "rtsp://admin:pass@192.168.1.101:554/stream1",
    "rtsp://admin:pass@192.168.1.102:554/stream1",
    "rtsp://admin:pass@192.168.1.103:554/stream1",
    "rtsp://admin:pass@192.168.1.104:554/stream1",
    "rtsp://admin:pass@192.168.1.105:554/stream1",
    "",
    "",
    ""
  ]
}
```

## Troubleshooting

### Connection Issues

- **"Failed to open stream"**: Check RTSP URL format, credentials, IP address, and port
- **"Multiple read failures"**: Camera may be offline or network issues. The app will automatically retry
- **Stream not displaying**: Verify the RTSP URL works in VLC or another RTSP client

### Performance Issues

- Reduce the number of streams if experiencing lag
- Check network bandwidth for multiple high-resolution streams
- Adjust `frame_update_interval` in the code for different frame rates

### Web Mode Issues

- **Can't access from other devices**: Ensure firewall allows connections on the specified port
- **Stream not updating**: Check browser console for errors, try refreshing the page
- **Port already in use**: Use `--port` to specify a different port

## Technical Details

- **Frame Rate**: ~30 FPS display update rate (configurable via `frame_update_interval`)
- **Tile Size**: 420x240 pixels (16:9 aspect ratio)
- **Video Encoding**: JPEG compression for web streaming
- **Threading**: Each stream runs in its own thread for parallel processing
- **Reconnection**: Exponential backoff from 2 seconds to 30 seconds maximum

## License

This project is provided as-is for personal and commercial use.

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.
