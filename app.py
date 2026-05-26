import csv
import math
import os
from flask import Flask, render_template, request, send_from_directory, jsonify, redirect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "master_table.csv")
IMAGE_DIR = os.path.join(BASE_DIR, "4k_for_vote")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Load catalogue once at startup
# ---------------------------------------------------------------------------

def load_catalogue():
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            # strip any leading/trailing whitespace from keys and values
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows

CATALOGUE = load_catalogue()

# Build a set of images that actually exist on disk for fast lookup
AVAILABLE_IMAGES = {
    fname[:-4]  # strip .png
    for fname in os.listdir(IMAGE_DIR)
    if fname.endswith(".png")
}


def row_has_image(row):
    return row.get("cutoutname", "") in AVAILABLE_IMAGES


def angular_distance(ra1, dec1, ra2, dec2):
    """Great-circle distance in degrees between two (RA, Dec) points."""
    ra1, dec1, ra2, dec2 = map(math.radians, [ra1, dec1, ra2, dec2])
    dra = ra2 - ra1
    ddec = dec2 - dec1
    a = math.sin(ddec / 2) ** 2 + math.cos(dec1) * math.cos(dec2) * math.sin(dra / 2) ** 2
    return math.degrees(2 * math.asin(math.sqrt(a)))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
@app.route("/research")
def research():
    return render_template("research.html", active_page="research")


@app.route("/lens-finder")
def lens_finder():
    return render_template("lens_finder.html", active_page="lens_finder")


@app.route("/cooray-group")
def cooray_group():
    return redirect("https://herschel.uci.edu/")


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    search_type = request.args.get("type", "auto").strip().lower()
    tolerance = float(request.args.get("tolerance", "0.01"))  # degrees

    if not query:
        return jsonify({"results": [], "error": "Please enter a search term."})

    results = []

    if search_type in ("objname", "auto"):
        # Case-insensitive substring match on objname
        q_lower = query.lower()
        for row in CATALOGUE:
            if q_lower in row.get("objname", "").lower():
                results.append(row)
        if results or search_type == "objname":
            return jsonify({"results": _format_results(results), "matched_on": "objname"})

    if search_type in ("ra", "auto"):
        try:
            ra_query = float(query)
            for row in CATALOGUE:
                try:
                    if abs(float(row["ra"]) - ra_query) <= tolerance:
                        results.append(row)
                except (ValueError, KeyError):
                    pass
            if results or search_type == "ra":
                return jsonify({"results": _format_results(results), "matched_on": "ra"})
        except ValueError:
            if search_type == "ra":
                return jsonify({"results": [], "error": "RA must be a numeric value."})

    if search_type in ("dec", "auto"):
        try:
            dec_query = float(query)
            for row in CATALOGUE:
                try:
                    if abs(float(row["dec"]) - dec_query) <= tolerance:
                        results.append(row)
                except (ValueError, KeyError):
                    pass
            if results or search_type == "dec":
                return jsonify({"results": _format_results(results), "matched_on": "dec"})
        except ValueError:
            if search_type == "dec":
                return jsonify({"results": [], "error": "Dec must be a numeric value."})

    if search_type == "coords":
        # Expect "RA,Dec" format
        parts = query.replace(";", ",").split(",")
        if len(parts) != 2:
            return jsonify({"results": [], "error": 'Coords search expects "RA,Dec" format.'})
        try:
            ra_q, dec_q = float(parts[0]), float(parts[1])
            for row in CATALOGUE:
                try:
                    dist = angular_distance(float(row["ra"]), float(row["dec"]), ra_q, dec_q)
                    if dist <= tolerance:
                        results.append({**row, "_distance": f"{dist:.6f}"})
                except (ValueError, KeyError):
                    pass
            results.sort(key=lambda r: float(r.get("_distance", 999)))
            return jsonify({"results": _format_results(results), "matched_on": "coords"})
        except ValueError:
            return jsonify({"results": [], "error": "Invalid coordinate format."})

    return jsonify({"results": _format_results(results), "matched_on": "auto"})


def _format_results(rows):
    out = []
    for row in rows:
        cutout = row.get("cutoutname", "")
        out.append({
            "index": row.get("index", ""),
            "cutoutname": cutout,
            "objname": row.get("objname", ""),
            "ra": row.get("ra", ""),
            "dec": row.get("dec", ""),
            "VIS": row.get("VIS", ""),
            "Y": row.get("Y", ""),
            "H": row.get("H", ""),
            "J": row.get("J", ""),
            "grade": row.get("grade", ""),
            "new": row.get("new", ""),
            "rawscore": row.get("rawscore", ""),
            "notes": row.get("notes", ""),
            "has_image": cutout in AVAILABLE_IMAGES,
            "_distance": row.get("_distance", ""),
        })
    return out


@app.route("/image/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGE_DIR, filename)


if __name__ == "__main__":
    print(f"Loaded {len(CATALOGUE)} objects from catalogue.")
    print(f"Found {len(AVAILABLE_IMAGES)} images in 4k_for_vote/.")
    app.run(host="0.0.0.0", port=5000)
