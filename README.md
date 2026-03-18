# AgriVision

AgriVision is a lightweight, fully automated pipeline that transforms drone imagery into:

- Orthophotos
- NDVI maps
- Grid-based crop health assessments
- A farmer-ready HTML report

It also integrates with the OpenAgri WeatherService for weather data and supports irrigation service configuration.

---

## Features

- Automatic image resizing
- ODM photogrammetry via Docker
- NDVI generation in **GeoTIFF** and **PNG** formats
- Grid-based crop health classification
- Automated field report generation
- Automatic WeatherService startup
- Compatible with **x86_64** and **ARM** devices

---

## One-Line Installation

```bash
curl -s https://raw.githubusercontent.com/GEvang/agrivision-pipeline/main/bootstrap.sh | bash
```

---

## Project Structure

```text
agrivision-pipeline/
├── agrivision/
│   ├── pipeline/
│   ├── utils/
│   ├── weather/
│   └── irrigation/
├── data/
├── output/
├── bootstrap.sh
├── install_agrivision.sh
├── cleanup.py
├── config.yaml
├── run.py
├── requirements.txt
└── .env.example
```

---

## Usage

### 1. Activate the virtual environment

```bash
source venv/bin/activate
```

### 2. Prepare your input data

- Copy drone images into the configured input folder
- Create a local `.env` file from `.env.example`

```bash
cp .env.example .env
```

### 3. Run the pipeline

```bash
python run.py
```

### 4. View the results

Open the generated HTML report in the `output/` folder.

---

## Weather Service

The WeatherService is started automatically if it is not already running.

Depending on the local environment, AgriVision uses Docker Compose when supported by the host setup.

---

## Configuration

Edit `config.yaml` to customize pipeline behavior, including:

- NDVI thresholds
- Camera band profiles
- Grid size
- Resize options
- Service base URLs
- Output paths

---

## Output

After processing completes, AgriVision generates outputs such as:

- Orthophotos
- NDVI raster and preview images
- Grid-based crop health summaries
- A farmer-friendly HTML report

---

## License

This project is licensed under the terms provided in the `LICENSE` file.
