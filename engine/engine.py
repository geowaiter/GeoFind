import os, io, json, base64, random, requests, torch, datetime, hashlib
import numpy as np
import torch.nn.functional as F
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from cryptography.fernet import Fernet 

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
HF_TOKEN = os.getenv("HF_TOKEN")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTERNAL_SALT = "GEOFIND_V1_STATIC_SALT"

LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

app = Flask(__name__)
CORS(app)

class GeoFIND:
    def __init__(self):
        self.model_id = "openai/clip-vit-large-patch14-336"

        self.config_path = os.path.join(BASE_DIR, "keys", "api.enc")

        self.api_key = self._load_key()

        print(f"[*] Initializing GeoFIND Engine on {DEVICE}...")
        self.model = CLIPModel.from_pretrained(self.model_id, token=HF_TOKEN).to(DEVICE)
        self.processor = CLIPProcessor.from_pretrained(self.model_id)

        landscapes = {
            "BENELUX": "stepped gables, flemish brick, bicycles, flat terrain, grey cobblestone, white license plates with red/black text",
            "NORDIC": "wooden slats, dark timber, clean modernism, fjord/pine backdrops, yellow road signs, minimalist design",
            "MEDIT": "terracotta roofs, ochre/white plaster, narrow stone alleys, vespas, dry climate, laundry on balconies",
            "DACH_ALPINE": "half-timbered houses, chalet balconies, mountains, gothic stone churches, ultra-clean infrastructure",
            "SOVIET_BLOC": "concrete panel blocks (plattenbau), cyrillic signs, wide soviet boulevards, rust, dense tram lines",
            "US_EAST": "red brick, fire escapes, row houses, blue street signs, dense asphalt, skyscrapers, steam",
            "US_WEST": "stucco, palm trees, sprawling wide boulevards, dry hills, freeway interchanges, glass towers",
            "LATAM": "unfinished red brick, colorful concrete, tropical greenery, tangled overhead wires, graffiti, hilly favelas",
            "ASIA_HI_TECH": "vending machines, kanji/hangul/hanzi, grey utility poles, neon, clean narrow streets, high density",
            "ASIA_TROPIC": "tuk-tuks, scooters, gold leaf temples, street food, lush palms, monsoon drains",
            "ARID_ARABIAN_PLATEAU": "tan masonry buildings, Riyadh Kingdom Tower style, sandy air, flat desert plains, Saudi license plates",
            "ARID_COASTAL_GULF": "hyper-modern glass spirals, Dubai Burj Khalifa style, coastal haze, palm islands, Emirates plates",
            "ANGLO_OCEANIA": "eucalyptus, left-side drive, yellow license plates, maritime light, Victorian suburbs"
        }

        matrix = {
            "KSA_RIYADH": (24.71, 46.67, "ARID_ARABIAN_PLATEAU", "Kingdom Centre, tan block buildings, vast flat desert roads"),
            "ARE_DUBAI": (25.20, 55.27, "ARID_COASTAL_GULF", "Burj Khalifa, coastal water, extreme glass verticality, Sheikh Zayed Road"),
            "ARE_ABU_DHABI": (24.45, 54.37, "ARID_COASTAL_GULF", "Ethihad Towers, white marble mosques, coastal corniche"),
            "QAT_DOHA": (25.28, 51.53, "ARID_COASTAL_GULF", "West Bay skyline, Museum of Islamic Art, pearl monument"),
            "BEL_BRU": (50.85, 4.35, "BENELUX", "Grand Place, gothic spire"),
            "BEL_ANT": (51.21, 4.40, "BENELUX", "Port docks, brick alleys"),
            "NLD_AMS": (52.36, 4.90, "BENELUX", "Canal rings, narrow brick"),
            "FRA_PAR": (48.85, 2.35, "MEDIT", "Haussmann limestone, zinc roofs"),
            "DEU_BER": (52.52, 13.40, "SOVIET_BLOC", "Graffiti, TV tower, U-Bahn"),
            "ITA_ROM": (41.90, 12.49, "MEDIT", "Ancient ruins, umbrella pines"),
            "ESP_BCN": (41.38, 2.17, "MEDIT", "Eixample grid, Sagrada Familia"),
            "GRC_ATH": (37.98, 23.72, "MEDIT", "Parthenon, white apartments, solar heaters"),
            "USA_NYC": (40.71, -74.00, "US_EAST", "Yellow cabs, grid iron, Manhattan"),
            "USA_CHI": (41.87, -87.62, "US_EAST", "Windy lakefront, El-train, brick industrial"),
            "USA_LAX": (34.05, -118.24, "US_WEST", "Hollywood hills, palm sprawl, freeways"),
            "USA_SFO": (37.77, -122.41, "US_WEST", "Golden Gate, fog, Victorian hills"),
            "MEX_CDMX": (19.43, -99.13, "LATAM", "Zocalo, jacaranda, dense wires"),
            "BRA_RJO": (-22.90, -43.17, "LATAM", "Sugarloaf, beach mosaic, favelas"),
            "ARG_BUE": (-34.60, -58.38, "MEDIT", "Parisian boulevards in South America"),
            "JPN_TOK": (35.67, 139.65, "ASIA_HI_TECH", "Shibuya neon, vending machines, clean streets"),
            "KOR_SEL": (37.56, 126.97, "ASIA_HI_TECH", "Hangul neon, dense apartments, Lotte Tower"),
            "CHN_SHA": (31.23, 121.47, "ASIA_HI_TECH", "Bund, futuristic skyscrapers, Oriental Pearl"),
            "THA_BKK": (13.75, 100.50, "ASIA_TROPIC", "Tuk-tuks, gold temples, street food"),
            "SGP_SGP": (1.35, 103.81, "ASIA_HI_TECH", "Marina Bay, green urbanism, pristine"),
            "AUS_SYD": (-33.86, 151.20, "ANGLO_OCEANIA", "Harbor bridge, opera house, blue water"),
            "EGY_CAI": (30.04, 31.23, "ARID_ARABIAN_PLATEAU", "Pyramids, Nile river, tan brick, heavy dust"),
            "ZAF_CPT": (-33.92, 18.42, "ANGLO_OCEANIA", "Table Mountain, Protea, coastal cliffs")
        }

        self.registry = {}
        for code, data in matrix.items():
            lat, lon, landscape_key, specific = data
            metadata = f"{landscapes[landscape_key]}, {specific}"
            self.registry[code] = (lat, lon, metadata)

        self.keys = list(self.registry.keys())
        self._cache_embeddings()

    def _load_key(self):
        if not os.path.exists(self.config_path):
            print(f"[!] Configuration missing: {self.config_path}")
            return None
        try:

            key = base64.urlsafe_b64encode(hashlib.sha256(INTERNAL_SALT.encode()).digest())
            cipher = Fernet(key)
            with open(self.config_path, 'rb') as f:
                data = f.read()
            return cipher.decrypt(data).decode('utf-8')
        except Exception:
            print(f"[!] Key verification failed. Path: {self.config_path}")
            return None

    def _cache_embeddings(self):
        prompts = [f"Location {k}: {v[2]}" for k, v in self.registry.items()]
        inputs = self.processor(text=prompts, return_tensors="pt", padding=True).to(DEVICE)
        with torch.no_grad():
            outputs = self.model.text_model(**inputs)
            features = self.model.text_projection(outputs.pooler_output)
            self.text_features = F.normalize(features, p=2, dim=-1)
        print(f"[+] GeoFIND Database Online. {len(self.keys)} regions indexed.")

    def log_entry(self, data):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(LOGS_DIR, f"log_{timestamp}.json")
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"[*] Session data saved: {path}")

    def analyze(self, image_bytes):
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = self.processor(images=img, return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            outputs = self.model.vision_model(**inputs)
            features = self.model.visual_projection(outputs.pooler_output)
            features = F.normalize(features, p=2, dim=-1)
            logits = (features @ self.text_features.T) * 100 
            probs = logits.softmax(dim=-1).squeeze()
            top_probs, top_idxs = torch.topk(probs, k=min(8, len(self.keys)))
            lat, lon, sum_p = 0.0, 0.0, top_probs.sum().item()
            matches = []
            for p, idx in zip(top_probs, top_idxs):
                weight = p.item() / (sum_p + 1e-6)
                data = self.registry[self.keys[idx.item()]]
                lat += data[0] * weight
                lon += data[1] * weight
                matches.append({"region": self.keys[idx.item()], "score": p.item()})
            return lat, lon, top_probs[0].item(), self.keys[top_idxs[0].item()], matches

ENGINE = GeoFIND()

@app.route('/api/image_geo', methods=['POST'])
def api_image_geo():
    try:
        payload = request.json.get('image_data')
        raw_img = base64.b64decode(payload.split(",")[-1])
        lat, lon, conf, region, matches = ENGINE.analyze(raw_img)
        entry = {
            "timestamp": str(datetime.datetime.now()),
            "coordinates": {"lat": lat, "lon": lon},
            "match": region,
            "confidence": float(conf),
            "alternatives": matches
        }
        ENGINE.log_entry(entry)
        return jsonify({
            "status": "GeoFIND ANALYSIS COMPLETE",
            "lat": lat, "lon": lon,
            "description": f"MATCH: {region} ({int(conf*100)}%)",
            "estimation": {"radius": int((1-conf)*100), "color": "#00ffcc"},
            "points": [{"lat": lat + random.uniform(-0.02, 0.02), "lon": lon + random.uniform(-0.02, 0.02)} for _ in range(50)]
        })
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/api/geo', methods=['POST'])
def api_network_geo():
    target = request.json.get('target', '0.0.0.0')
    return jsonify({
        "status": "GeoFIND Network Trace",
        "lat": 50.8503, "lon": 4.3517,
        "description": f"IP: {target} (Location: Brussels, BE)",
        "estimation": {"radius": 5, "color": "#55ffff"},
        "points": []
    })

@app.route('/api/breach', methods=['POST'])
def api_breach():
    email = request.json.get('email', '')
    if not ENGINE.api_key:
        return jsonify({"status": "error", "message": "Key verification required.", "results": []}), 403

    url = "https://www.osintcat.net/api/breach"
    params = {"query": email}
    headers = {"X-API-KEY": ENGINE.api_key}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=12)
        if response.ok:
            data = response.json()
            ENGINE.log_entry({"type": "lookup", "query": email, "hits": data.get("results_count", 0)})
            return jsonify(data)
        return jsonify({"status": "error", "message": f"Service unavailable: {response.status_code}"}), response.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": "Connection timed out."}), 500

@app.route('/')
def ui():

    return send_from_directory(BASE_DIR, 'index.html')

if __name__ == "__main__":
    print("[+] GeoFIND v1.0.0 ONLINE - PRODUCTION MODE")
    app.run(port=5000, host="0.0.0.0", debug=False, threaded=True)