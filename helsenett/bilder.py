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
    else:
        body = (x / 0.85) ** 2 + ((y + 0.05) / 1.05) ** 2 < 1
        lungs = (((np.abs(x) - 0.36) / 0.26) ** 2 + ((y + 0.05) / 0.62) ** 2) < 1
        spine = np.abs(x) < 0.06
        ribs = (np.sin(y * 28 + np.abs(x) * 6) > 0.75) & lungs
        heart = ((x + 0.12) / 0.26) ** 2 + ((y - 0.2) / 0.3) ** 2 < 1
        image = body * 0.75 - lungs * 0.55 + spine * 0.25 + ribs * 0.25 + heart * lungs * 0.35
        sop_class = "1.2.840.10008.5.1.4.1.1.1.1"  # Digital X-Ray Image Storage
    image = np.clip(image + rng.normal(0, 0.02, image.shape), 0, 1)
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
    ds.Rows = ds.Columns = size
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
