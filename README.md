# AgriVision Pipeline

A lightweight, automated drone-image processing pipeline for generating orthophotos, NDVI vegetation health maps, and future agricultural risk analysis on a Linux mini-PC.

AgriVision is designed to run fully automated after a drone flight:

Drone lands

Photos auto-upload to the mini-PC

Images resize

ODM generates the orthophoto

NDVI map is computed

(future) Weather, soil, pest data integrated

Farmer receives plant-health results

📂 Project Structure
agrivision-pipeline/
 ├─ scripts/
 │   ├─ resize_images.py
 │   ├─ run_odm.py
 │   ├─ compute_ndvi.py
 │   └─ ndvi_pipeline.py   <-- main controller
 ├─ data/
 │   ├─ images_full/       <-- original drone images
 │   ├─ images_resized/    <-- resized images for faster ODM
 │   └─ odm_project/       <-- ODM project output structure
 ├─ output/
 │   ├─ orthos/            <-- final orthophotos (optional)
 │   └─ ndvi/              <-- NDVI GeoTIFF + color PNG
 ├─ config/                <-- future camera & pipeline configs
 ├─ venv/                  <-- Python virtual environment
 ├─ README.md
 ├─ .gitignore
 └─ requirements.txt (future)


🔧 Installation (Linux / Ubuntu)
1. Clone the repository
git clone https://github.com/GEvang/agrivision-pipeline.git
cd agrivision-pipeline

2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

3. Install Python dependencies
pip install pillow rasterio numpy matplotlib

4. Install Docker (ODM runs in a container)
sudo apt install docker.io
sudo usermod -aG docker $USER


Log out and back in after adding yourself to the docker group.

5. Pull OpenDroneMap Docker image
docker pull opendronemap/odm:latest

▶️ How to Run the Entire Pipeline

From the project root:

source venv/bin/activate
python3 scripts/ndvi_pipeline.py


This will:

Resize images

Run ODM

Compute NDVI

All outputs will be produced automatically.

⚙️ Pipeline Options
Skip ODM (if you already have an orthophoto)
python3 scripts/ndvi_pipeline.py --skip-odm

Skip resizing (if images are already resized)
python3 scripts/ndvi_pipeline.py --skip-resize

Run only NDVI on an existing orthophoto
python3 scripts/ndvi_pipeline.py --skip-resize --skip-odm

Skip everything (test only)
python3 scripts/ndvi_pipeline.py --skip-resize --skip-odm --skip-ndvi
