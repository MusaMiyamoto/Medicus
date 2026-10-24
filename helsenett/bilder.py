"""Medical images: check uploads, show DICOM (X-ray, CT, MR) as PNG, and make synthetic test images.

DICOM is the standard every radiology system (PACS) uses, so images from any provider can be
shared the same way. Only uncompressed DICOM is shown in this prototype; compressed transfer
syntaxes need an extra decoder (e.g. pylibjpeg) and can still be downloaded.
"""

import io
from datetime import date

ALLOWED = {
    "dicom": "application/dicom",
    "png": "image/png",
    "jpeg": "image/jpeg",
    "pdf": "application/pdf",
}
MAX_BYTES = 50 * 1024 * 1024


class BildeFeil(ValueError):
    pass


def kind_of(data: bytes) -> str:
    """Decide the file type from its content, never from the file name."""
    if len(data) > 132 and data[128:132] == b"DICM":
        return "dicom"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"%PDF-"):
        return "pdf"
    raise BildeFeil("Bare DICOM, PNG, JPEG og PDF kan deles.")


def dicom_info(data: bytes) -> dict:
    import pydicom

    ds = pydicom.dcmread(io.BytesIO(data), stop_before_pixels=True)
    raw_date = str(ds.get("StudyDate", ""))
    return {
        "modalitet": str(ds.get("Modality", "")),
        "undersokelse": str(ds.get("StudyDescription", "")),
        "kroppsdel": str(ds.get("BodyPartExamined", "")),
        "dato": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if len(raw_date) == 8 else "",
        "merknad": str(ds.get("ImageComments", "")),
    }


def render_png(data: bytes, max_side: int = 1024) -> bytes:
    from PIL import Image

    kind = kind_of(data)
    if kind == "pdf":
        raise BildeFeil("PDF kan lastes ned, men ikke forhåndsvises.")
    if kind == "dicom":
        image = _dicom_image(data)
    else:
        image = Image.open(io.BytesIO(data))
        image.load()
        image = image.convert("RGB" if image.mode not in ("L", "RGB") else image.mode)
    image.thumbnail((max_side, max_side))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _dicom_image(data: bytes):
    import numpy as np
    import pydicom
    from PIL import Image

    try:
        from pydicom.pixels import apply_voi_lut
    except ImportError:  # pydicom 2.x
        from pydicom.pixel_data_handlers.util import apply_voi_lut

    ds = pydicom.dcmread(io.BytesIO(data))
    try:
        pixels = ds.pixel_array
    except Exception as e:
        raise BildeFeil("Bildet er komprimert på en måte som ikke kan vises her ennå. Last det ned.") from e
    if pixels.ndim == 3 and ds.get("SamplesPerPixel", 1) == 1:
        pixels = pixels[len(pixels) // 2]  # a series: show the middle slice
    pixels = apply_voi_lut(pixels, ds).astype("float64")
    low, high = float(pixels.min()), float(pixels.max())
    scaled = (pixels - low) / (high - low or 1) * 255
    if ds.get("PhotometricInterpretation") == "MONOCHROME1":
        scaled = 255 - scaled
    return Image.fromarray(scaled.astype(np.uint8))


def _soft(d, width):
    """0 outside, 1 inside, with a soft edge: d is a signed distance (positive inside)."""
    import numpy as np
    return 1 / (1 + np.exp(-d / width))


def _band(dist, half, edge):
    """A soft stripe around a curve: dist is the distance from the curve's centre line."""
    import numpy as np
    return _soft(half - np.abs(dist), edge)


def _blur(image, sigma):
    """Gaussian blur through the FFT (no scipy needed)."""
    import numpy as np
    h, w = image.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    kernel = np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(image) * kernel))


def _chest(size, rng):
    """A made-up PA chest X-ray, drawn from simple shapes. Bright = dense, as on a real film."""
    import numpy as np
    soft, band, blur = _soft, _band, _blur
    y, x = np.mgrid[-1:1:size * 1j, -1:1:size * 1j]
    ax = np.abs(x)

    # Torso: narrow neck, shoulders, then the chest wall.
    half_width = np.interp(y, [-1, -0.82, -0.62, -0.45, 0.2, 1], [0.24, 0.3, 0.9, 0.93, 0.9, 0.86])
    body = soft(half_width - ax, 0.008)
    image = 0.42 * body

    # Shoulders: humeral heads and the edge of the shoulder blades.
    for side in (-1, 1):
        head = np.hypot(x - side * 0.86, (y + 0.6) / 1.1)
        image += 0.2 * soft(0.11 - head, 0.01) * body
        scapula = band(ax - (0.66 + 0.18 * (y + 0.6)), 0.015, 0.006) * soft(0.25 - np.abs(y + 0.35), 0.02)
        image += 0.06 * scapula * body

    # Lungs: apex at the top, rounded domes of the diaphragm below, deeper at the sides.
    outer = np.interp(y, [-0.62, -0.5, -0.3, 0.1, 0.5], [0.3, 0.55, 0.72, 0.8, 0.82])
    left_heart_border = np.interp(y, [-0.6, -0.1, 0.15, 0.4, 0.55], [0.14, 0.15, 0.3, 0.42, 0.44])
    right_heart_border = np.interp(y, [-0.6, -0.1, 0.25, 0.5], [0.12, 0.13, 0.2, 0.22])
    inner = np.where(x > 0, left_heart_border, right_heart_border)
    dome = np.where(x > 0, 0.42, 0.36) - 0.18 * ((ax - 0.45) / 0.4) ** 2  # the right dome sits higher
    apex = -0.66 + 0.5 * ((ax - 0.42) / 0.3) ** 2
    lung = soft(outer - ax, 0.03) * soft(ax - inner, 0.025) * soft(dome - y, 0.03) * soft(y - apex, 0.03)
    image -= 0.3 * lung * (0.75 + 0.25 * soft(ax - inner - 0.15, 0.08))

    # Vessels: fine markings, strongest near the hila and fading towards the edges.
    noise = blur(rng.normal(0, 1, (size, size)), size / 160) - blur(rng.normal(0, 1, (size, size)), size / 60)
    streaks = np.clip(noise * 6, 0, None)
    hilum = np.exp(-(((ax - 0.22) / 0.28) ** 2 + ((y + 0.05) / 0.35) ** 2))
    image += lung * (0.08 * streaks * (0.4 + hilum) + 0.06 * hilum)

    # Posterior ribs (curving out and down from the spine) and fainter anterior ribs.
    ribs = np.zeros_like(x)
    for k in range(10):
        top = -0.6 + 0.105 * k
        u = ax - 0.07
        curve = top - 0.22 * u + 0.62 * u ** 2
        reach = soft(half_width - 0.05 - ax, 0.01) * soft(u, 0.005)
        ribs += band(y - curve, 0.02 + 0.006 * u, 0.004) * reach
        front = top + 0.12 + 0.32 * (0.82 - ax)
        ribs += 0.4 * band(y - front, 0.014, 0.004) * soft(ax - 0.28, 0.03) * soft(0.82 - ax, 0.02)
    image += 0.075 * np.clip(ribs, 0, 1.4) * body * soft(dome + 0.1 - y, 0.04)

    # Clavicles: an S from the top of the sternum out to the shoulders.
    clav_y = -0.66 - 0.1 * (ax - 0.12) + 0.05 * np.sin((ax - 0.12) * 6)
    image += 0.2 * band(y - clav_y, 0.028, 0.01) * soft(ax - 0.1, 0.01) * soft(0.76 - ax, 0.02)

    # Mediastinum and heart: dense in the middle, widening to the patient's left (image right).
    mediastinum = soft(inner + 0.02 - ax, 0.03) * soft(dome + 0.03 - y, 0.03) * soft(y + 0.75, 0.05)
    heart = soft(1 - np.hypot((x - 0.08) / 0.36, (y - 0.2) / 0.3), 0.03) * soft(dome + 0.02 - y, 0.015)
    image += 0.2 * np.maximum(mediastinum, heart) * body

    # Spine: vertebrae with disc spaces; the trachea is air.
    discs = 0.5 + 0.5 * np.cos(np.pi * (y + 1) / 0.105)
    image += (0.1 + 0.04 * discs) * band(x, 0.065, 0.01) * body
    image -= 0.12 * band(x + 0.01, 0.028, 0.008) * soft(-0.22 - y, 0.02)

    # Below the diaphragm: liver on the right, stomach gas bubble on the left.
    belly = soft(y - dome, 0.03) * body
    image += 0.08 * belly * soft(-x, 0.2)
    image -= 0.14 * soft(1 - np.hypot((x - 0.42) / 0.13, (y - 0.56) / 0.07), 0.1) * belly

    image = blur(image, size / 700) + rng.normal(0, 0.012, image.shape)
    return np.clip(image * 1.15, 0, 1) ** 1.1


def synthetic_dicom(name: str, patient_id: str, modality: str, description: str, body_part: str) -> bytes:
    """A made-up image that looks roughly like an X-ray or MR slice. Clearly marked as synthetic."""
    import numpy as np
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    size = 512
    y, x = np.mgrid[-1:1:size * 1j, -1:1:size * 1j]
    rng = np.random.default_rng(7)
    if modality == "MR":
        head = (x / 0.72) ** 2 + (y / 0.88) ** 2 < 1
        brain = (x / 0.64) ** 2 + (y / 0.8) ** 2 < 1
        folds = 0.5 + 0.5 * np.sin(18 * np.hypot(x, y) + 6 * np.arctan2(y, x))
        ventricles = ((np.abs(x) - 0.12) / 0.07) ** 2 + (y / 0.22) ** 2 < 1
        image = head * 0.35 + brain * (0.45 + 0.2 * folds) - ventricles * 0.6
        sop_class = "1.2.840.10008.5.1.4.1.1.4"  # MR Image Storage
        image = image + rng.normal(0, 0.02, image.shape)
    else:
        image = _chest(768, rng)
        sop_class = "1.2.840.10008.5.1.4.1.1.1.1"  # Digital X-Ray Image Storage
    image = np.clip(image, 0, 1)
    pixels = (image * 4095).astype(np.uint16)

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = sop_class
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = Dataset()
    ds.file_meta = meta
    ds.preamble = b"\0" * 128
    ds.SOPClassUID = sop_class
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.PatientName = name.replace(" ", "^")
    ds.PatientID = patient_id
    ds.Modality = modality
    ds.StudyDescription = description
    ds.BodyPartExamined = body_part
    ds.StudyDate = date.today().strftime("%Y%m%d")
    ds.ImageComments = "SYNTETISK TESTBILDE - ikke en ekte pasient"
    ds.Rows, ds.Columns = pixels.shape
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.WindowCenter = 2048
    ds.WindowWidth = 4096
    ds.PixelData = pixels.tobytes()
    out = io.BytesIO()
    try:
        ds.save_as(out, enforce_file_format=True)
    except TypeError:  # pydicom 2.x
        ds.is_little_endian, ds.is_implicit_VR = True, False
        ds.save_as(out, write_like_original=False)
    return out.getvalue()
