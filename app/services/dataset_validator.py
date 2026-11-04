import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import yaml
from PIL import Image

from app.models.dataset import DatasetStatus

# Canonical 12 Civic Classes (Strict Zero-Indexed Mapping)
CANONICAL_CLASSES: Dict[int, str] = {
    0: "Garbage Overflow",
    1: "Illegal Dumping",
    2: "Pothole",
    3: "Damaged Road",
    4: "Water Leakage",
    5: "Sewage Overflow",
    6: "Broken Street Light",
    7: "Drainage Problem",
    8: "Traffic Issue",
    9: "Building Damage",
    10: "Park/Public Space Damage",
    11: "Environmental Pollution",
}

# Reverse lookup
CANONICAL_NAME_TO_ID: Dict[str, int] = {v.lower(): k for k, v in CANONICAL_CLASSES.items()}

# Supported file formats
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SUPPORTED_LABEL_EXTENSIONS = {".txt"}
SPLIT_NAMES = ["train", "val", "test"]


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class YOLOValidationResult:
    def __init__(self, dataset_version: str):
        self.dataset_version = dataset_version
        self.is_valid = True
        self.status = DatasetStatus.READY_FOR_TRAINING
        self.summary = {
            "train_images": 0,
            "val_images": 0,
            "test_images": 0,
            "total_images": 0,
            "total_objects": 0,
            "class_count": 0,
            "empty_label_count": 0,
            "missing_label_count": 0,
            "orphan_label_count": 0,
            "invalid_label_count": 0,
            "corrupted_image_count": 0,
            "duplicate_image_count": 0,
            "duplicate_group_count": 0,
        }
        self.splits = {
            "train": {"images": 0, "annotated_images": 0, "objects": 0, "percentage": 0.0},
            "val": {"images": 0, "annotated_images": 0, "objects": 0, "percentage": 0.0},
            "test": {"images": 0, "annotated_images": 0, "objects": 0, "percentage": 0.0},
        }
        self.classes: List[Dict[str, Any]] = []
        self.missing_labels: List[Dict[str, str]] = []
        self.orphan_labels: List[Dict[str, str]] = []
        self.invalid_labels: List[Dict[str, Any]] = []
        self.corrupted_images: List[Dict[str, Any]] = []
        self.duplicate_images: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def add_error(self, message: str):
        self.errors.append(message)
        self.is_valid = False
        self.status = DatasetStatus.INVALID

    def add_warning(self, message: str):
        self.warnings.append(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "valid": self.is_valid,
            "status": self.status,
            "summary": self.summary,
            "splits": self.splits,
            "classes": self.classes,
            "missing_labels": self.missing_labels,
            "orphan_labels": self.orphan_labels,
            "invalid_labels": self.invalid_labels,
            "corrupted_images": self.corrupted_images,
            "duplicate_images": self.duplicate_images,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class YOLODatasetValidator:
    """
    Validates YOLO dataset structure, data.yaml configuration, image integrity,
    and label coordinate bounds according to civic issue requirements.
    """

    def __init__(self, dataset_dir: Path, dataset_version: str):
        self.dataset_dir = Path(dataset_dir).resolve()
        self.dataset_version = dataset_version
        self.result = YOLOValidationResult(dataset_version)

    def validate(self) -> YOLOValidationResult:
        """Run complete dataset validation sequence."""
        if not self.dataset_dir.exists() or not self.dataset_dir.is_dir():
            self.result.add_error(f"Dataset root directory does not exist: {self.dataset_dir}")
            return self.result

        # 1. Validate required directory structure
        self._validate_directory_structure()

        # 2. Validate data.yaml configuration
        declared_classes = self._validate_data_yaml()

        # 3. If critical structural errors or missing yaml already occurred, still validate files if directories exist
        self._validate_images_and_labels(declared_classes)

        # 4. Final status determination
        if self.result.errors:
            self.result.is_valid = False
            self.result.status = DatasetStatus.INVALID
        else:
            self.result.is_valid = True
            self.result.status = DatasetStatus.READY_FOR_TRAINING

        return self.result

    def _validate_directory_structure(self):
        """Ensure images/ and labels/ subdirectories exist for train, val, test."""
        for split in SPLIT_NAMES:
            img_dir = self.dataset_dir / "images" / split
            lbl_dir = self.dataset_dir / "labels" / split

            if not img_dir.exists() or not img_dir.is_dir():
                self.result.add_error(f"Missing required image directory: images/{split}")
            if not lbl_dir.exists() or not lbl_dir.is_dir():
                self.result.add_error(f"Missing required label directory: labels/{split}")

    def _validate_data_yaml(self) -> Dict[int, str]:
        """
        Validate data.yaml:
        - Must exist and be readable.
        - Must specify train, val, test paths and names.
        - Resolves relative paths safely.
        - Checks class mapping against canonical 12 civic classes.
        """
        yaml_path = self.dataset_dir / "data.yaml"
        if not yaml_path.exists():
            self.result.add_error("Missing required data.yaml at dataset root.")
            return {}

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except Exception as exc:
            self.result.add_error(f"Unreadable or malformed data.yaml: {str(exc)}")
            return {}

        if not isinstance(config, dict):
            self.result.add_error("data.yaml must be a valid YAML dictionary.")
            return {}

        # Check required keys
        for key in ["train", "val", "test", "names"]:
            if key not in config or config[key] is None:
                self.result.add_error(f"data.yaml is missing required key '{key}'.")

        # Resolve paths
        base_path = self.dataset_dir
        if "path" in config and config["path"]:
            declared_path = Path(config["path"])
            if not declared_path.is_absolute():
                base_path = (self.dataset_dir / declared_path).resolve()
            else:
                base_path = declared_path

        for split in ["train", "val", "test"]:
            if split in config and config[split]:
                split_path = Path(config[split])
                resolved = split_path if split_path.is_absolute() else (base_path / split_path).resolve()
                if not resolved.exists():
                    self.result.add_error(f"Declared {split} path does not exist on disk: {config[split]}")

        # Validate names
        declared_classes: Dict[int, str] = {}
        raw_names = config.get("names")
        if raw_names is not None:
            if isinstance(raw_names, list):
                for idx, name in enumerate(raw_names):
                    declared_classes[idx] = str(name).strip()
            elif isinstance(raw_names, dict):
                for k, v in raw_names.items():
                    try:
                        declared_classes[int(k)] = str(v).strip()
                    except ValueError:
                        self.result.add_error(f"Invalid non-integer class ID in data.yaml names: '{k}'")
            else:
                self.result.add_error("data.yaml 'names' must be a list or dictionary.")

        # Check for duplicated class names
        seen_names = set()
        for c_id, c_name in declared_classes.items():
            norm_name = c_name.lower()
            if norm_name in seen_names:
                self.result.add_error(f"Duplicate class name in data.yaml: '{c_name}'")
            seen_names.add(norm_name)

        # Check against canonical 12 classes
        conflicts = []
        for c_id, c_name in declared_classes.items():
            if c_id not in CANONICAL_CLASSES:
                conflicts.append(f"Class ID {c_id} ('{c_name}') is outside canonical range 0..11.")
            else:
                canonical_name = CANONICAL_CLASSES[c_id]
                if c_name.lower() != canonical_name.lower():
                    conflicts.append(
                        f"Class ID {c_id} is declared as '{c_name}' but canonical class {c_id} is '{canonical_name}'."
                    )

        if conflicts:
            for conf in conflicts:
                self.result.add_error(conf)

        # Subset warning check
        num_classes = len(declared_classes)
        self.result.summary["class_count"] = num_classes
        if 0 < num_classes < 12 and not conflicts:
            self.result.add_warning(f"Dataset contains {num_classes} of 12 required civic classes.")
        elif num_classes == 0:
            self.result.add_error("Dataset data.yaml declares zero classes.")

        return declared_classes

    def _validate_images_and_labels(self, declared_classes: Dict[int, str]):
        """
        Validate images (extensions, Pillow integrity, SHA-256 duplicate detection)
        and labels (format, normalized coordinate bounds, class ID validity).
        """
        image_hashes: Dict[str, List[Path]] = {}
        class_object_counts: Dict[int, int] = {c: 0 for c in declared_classes}
        class_image_counts: Dict[int, set] = {c: set() for c in declared_classes}

        total_images = 0
        total_objects = 0
        empty_label_count = 0

        for split in SPLIT_NAMES:
            img_dir = self.dataset_dir / "images" / split
            lbl_dir = self.dataset_dir / "labels" / split

            if not img_dir.exists() or not lbl_dir.exists():
                continue

            # Gather image files
            split_images: Dict[str, Path] = {}
            for item in img_dir.iterdir():
                if item.is_file():
                    ext = item.suffix.lower()
                    if ext in SUPPORTED_IMAGE_EXTENSIONS:
                        split_images[item.stem] = item
                    else:
                        self.result.add_warning(f"Unsupported file format ignored in images/{split}: {item.name}")

            # Gather label files
            split_labels: Dict[str, Path] = {}
            for item in lbl_dir.iterdir():
                if item.is_file():
                    ext = item.suffix.lower()
                    if ext in SUPPORTED_LABEL_EXTENSIONS:
                        split_labels[item.stem] = item
                    else:
                        self.result.add_warning(f"Unsupported file format ignored in labels/{split}: {item.name}")

            split_img_count = len(split_images)
            total_images += split_img_count
            self.result.summary[f"{split}_images"] = split_img_count
            self.result.splits[split]["images"] = split_img_count

            annotated_images_count = 0
            split_objects_count = 0

            # Image integrity & duplicate check
            for stem, img_path in split_images.items():
                rel_img_path = img_path.relative_to(self.dataset_dir).as_posix()

                # Pillow verification
                try:
                    with Image.open(img_path) as im:
                        im.verify()
                except Exception as exc:
                    self.result.corrupted_images.append({
                        "file": rel_img_path,
                        "error": str(exc),
                    })
                    self.result.add_error(f"Corrupted image file: {rel_img_path} ({str(exc)})")
                    continue

                # SHA-256 hash for exact duplicate detection
                try:
                    h = compute_file_sha256(img_path)
                    image_hashes.setdefault(h, []).append(img_path)
                except Exception:
                    pass

                # Check for corresponding label
                if stem not in split_labels:
                    expected_lbl = f"labels/{split}/{stem}.txt"
                    self.result.missing_labels.append({
                        "image": rel_img_path,
                        "expected_label": expected_lbl,
                    })

            # Check for orphan labels
            for stem, lbl_path in split_labels.items():
                rel_lbl_path = lbl_path.relative_to(self.dataset_dir).as_posix()
                if stem not in split_images:
                    self.result.orphan_labels.append({
                        "label": rel_lbl_path,
                    })

            # Parse label files
            for stem, lbl_path in split_labels.items():
                rel_lbl_path = lbl_path.relative_to(self.dataset_dir).as_posix()

                try:
                    with open(lbl_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except Exception as exc:
                    self.result.invalid_labels.append({
                        "file": rel_lbl_path,
                        "line": 0,
                        "content": "",
                        "error": f"Failed to read label file: {str(exc)}",
                    })
                    self.result.add_error(f"Unreadable label file: {rel_lbl_path}")
                    continue

                # Non-empty lines
                valid_rows = [l.strip() for l in lines if l.strip()]
                if not valid_rows:
                    empty_label_count += 1
                    continue

                file_has_valid_objects = False
                for line_num, line_str in enumerate(lines, start=1):
                    stripped = line_str.strip()
                    if not stripped:
                        continue

                    tokens = stripped.split()
                    if len(tokens) != 5:
                        err_msg = f"Expected 5 values (class_id x_center y_center width height), found {len(tokens)}"
                        self.result.invalid_labels.append({
                            "file": rel_lbl_path,
                            "line": line_num,
                            "content": stripped,
                            "error": err_msg,
                        })
                        self.result.add_error(f"Malformed label in {rel_lbl_path}:{line_num} - {err_msg}")
                        continue

                    # Parse class ID
                    try:
                        c_id = int(tokens[0])
                    except ValueError:
                        err_msg = f"class_id '{tokens[0]}' is not an integer."
                        self.result.invalid_labels.append({
                            "file": rel_lbl_path,
                            "line": line_num,
                            "content": stripped,
                            "error": err_msg,
                        })
                        self.result.add_error(f"Invalid label in {rel_lbl_path}:{line_num} - {err_msg}")
                        continue

                    # Validate class ID bounds
                    if declared_classes and c_id not in declared_classes:
                        err_msg = f"class_id {c_id} is not declared in data.yaml classes {list(declared_classes.keys())}."
                        self.result.invalid_labels.append({
                            "file": rel_lbl_path,
                            "line": line_num,
                            "content": stripped,
                            "error": err_msg,
                        })
                        self.result.add_error(f"Invalid class ID in {rel_lbl_path}:{line_num} - {err_msg}")
                        continue

                    # Parse coordinates
                    try:
                        xc = float(tokens[1])
                        yc = float(tokens[2])
                        w = float(tokens[3])
                        h = float(tokens[4])
                    except ValueError:
                        err_msg = "Bounding box coordinates must be floating point numbers."
                        self.result.invalid_labels.append({
                            "file": rel_lbl_path,
                            "line": line_num,
                            "content": stripped,
                            "error": err_msg,
                        })
                        self.result.add_error(f"Invalid coordinates in {rel_lbl_path}:{line_num} - {err_msg}")
                        continue

                    # Validate coordinate ranges: 0 <= xc, yc <= 1, 0 < w, h <= 1
                    coord_error = None
                    if not (0.0 <= xc <= 1.0):
                        coord_error = f"x_center {xc} is outside [0.0, 1.0]"
                    elif not (0.0 <= yc <= 1.0):
                        coord_error = f"y_center {yc} is outside [0.0, 1.0]"
                    elif not (0.0 < w <= 1.0):
                        coord_error = f"width {w} must be in (0.0, 1.0]"
                    elif not (0.0 < h <= 1.0):
                        coord_error = f"height {h} must be in (0.0, 1.0]"

                    if coord_error:
                        self.result.invalid_labels.append({
                            "file": rel_lbl_path,
                            "line": line_num,
                            "content": stripped,
                            "error": coord_error,
                        })
                        self.result.add_error(f"Out of bounds coordinates in {rel_lbl_path}:{line_num} - {coord_error}")
                        continue

                    # Record valid object
                    file_has_valid_objects = True
                    split_objects_count += 1
                    total_objects += 1
                    class_object_counts[c_id] = class_object_counts.get(c_id, 0) + 1
                    class_image_counts.setdefault(c_id, set()).add(stem)

                if file_has_valid_objects:
                    annotated_images_count += 1

            self.result.splits[split]["annotated_images"] = annotated_images_count
            self.result.splits[split]["objects"] = split_objects_count

        # Update summary counts
        self.result.summary["total_images"] = total_images
        self.result.summary["total_objects"] = total_objects
        self.result.summary["empty_label_count"] = empty_label_count
        self.result.summary["missing_label_count"] = len(self.result.missing_labels)
        self.result.summary["orphan_label_count"] = len(self.result.orphan_labels)
        self.result.summary["invalid_label_count"] = len(self.result.invalid_labels)
        self.result.summary["corrupted_image_count"] = len(self.result.corrupted_images)

        # Informative warnings for empty labels, missing labels, orphan labels
        if empty_label_count > 0:
            self.result.add_warning(f"Dataset contains {empty_label_count} empty label files (background/negative samples).")
        if self.result.missing_labels:
            self.result.add_warning(f"Detected {len(self.result.missing_labels)} images missing corresponding label files.")
        if self.result.orphan_labels:
            self.result.add_warning(f"Detected {len(self.result.orphan_labels)} orphan label files without corresponding images.")

        # Compute split percentages
        for split in SPLIT_NAMES:
            img_c = self.result.splits[split]["images"]
            pct = round((img_c / total_images * 100.0), 2) if total_images > 0 else 0.0
            self.result.splits[split]["percentage"] = pct

        # Duplicate images check
        dup_groups = 0
        dup_total_files = 0
        for h, file_list in image_hashes.items():
            if len(file_list) > 1:
                dup_groups += 1
                dup_total_files += len(file_list)
                rel_paths = [p.relative_to(self.dataset_dir).as_posix() for p in file_list]
                self.result.duplicate_images.append({
                    "sha256": h,
                    "count": len(file_list),
                    "files": rel_paths,
                })

        self.result.summary["duplicate_group_count"] = dup_groups
        self.result.summary["duplicate_image_count"] = dup_total_files
        if dup_groups > 0:
            self.result.add_warning(f"Detected {dup_total_files} exact duplicate images across {dup_groups} unique hash groups.")

        # Build class distribution statistics
        self.result.classes = []
        for c_id in sorted(declared_classes.keys()):
            c_name = declared_classes[c_id]
            obj_c = class_object_counts.get(c_id, 0)
            img_set = class_image_counts.get(c_id, set())
            pct = round((obj_c / total_objects * 100.0), 2) if total_objects > 0 else 0.0

            self.result.classes.append({
                "class_id": c_id,
                "class_name": c_name,
                "images": len(img_set),
                "objects": obj_c,
                "percentage": pct,
            })
