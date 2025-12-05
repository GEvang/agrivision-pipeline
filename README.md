AgriVision is a lightweight, fully automated pipeline for processing drone imagery into orthophotos, NDVI maps, grid-based health assessments, and a farmer-ready HTML report. It integrates seamlessly with the OpenAgri WeatherService for real-time weather data.

Features
- Automatic image resizing
- ODM photogrammetry via Docker
- NDVI computation (GeoTIFF + PNG)
- Grid-based crop health classification
- Field report generation (report_latest.html)
- Automatic WeatherService startup
- Works on x86_64 and ARM devices

One-Line Installation
curl -s https://raw.githubusercontent.com/GEvang/agrivision-pipeline/main/bootstrap.sh | bash

Project Structure
agrivision-ads/
  agrivision/
    pipeline/
    utils/
    weather/
  data/
  output/
  OpenAgri-WeatherService/
  install_agrivision.sh
  bootstrap.sh
  config.yaml
  run.py
  venv/

Usage
1. Activate environment:
   source venv/bin/activate
2. Copy drone images to data/images_full/
3. Run pipeline:
   python run.py
4. Open output/report_latest.html

Weather Service
Automatically started if not running using docker compose.

Configuration
Edit config.yaml to adjust NDVI thresholds, camera bands, grid size, resize options, WeatherService URL, etc.


