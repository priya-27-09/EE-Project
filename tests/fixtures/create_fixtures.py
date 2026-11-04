import io
from pathlib import Path
from PIL import Image

FIXTURE_DIR = Path(__file__).resolve().parent / "yolo_dataset"


def build_synthetic_fixture():
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. README
    readme = (
        "# Synthetic YOLO Test Dataset Fixture\n\n"
        "IMPORTANT NOTICE:\n"
        "This is a SMALL, SYNTHETIC dataset created ONLY for automated testing of YOLO dataset validation logic.\n"
        "It contains synthetic dummy test images and valid bounding box coordinates.\n"
        "It is NOT a real civic dataset and is NEVER used for AI model training or inference.\n"
    )
    with open(FIXTURE_DIR / "README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    # 2. data.yaml
    data_yaml = (
        "path: .\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n\n"
        "names:\n"
        "  0: Garbage Overflow\n"
        "  1: Illegal Dumping\n"
        "  2: Pothole\n"
        "  3: Damaged Road\n"
    )
    with open(FIXTURE_DIR / "data.yaml", "w", encoding="utf-8") as f:
        f.write(data_yaml)

    # 3. Create split dirs
    for split in ["train", "val", "test"]:
        (FIXTURE_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (FIXTURE_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    # 4. Generate tiny Pillow images and matching labels
    # train
    im1 = Image.new("RGB", (128, 128), color=(200, 100, 50))
    im1.save(FIXTURE_DIR / "images" / "train" / "pothole_sample01.jpg")
    with open(FIXTURE_DIR / "labels" / "train" / "pothole_sample01.txt", "w") as f:
        f.write("2 0.50 0.50 0.30 0.30\n3 0.25 0.35 0.20 0.15\n")

    im2 = Image.new("RGB", (128, 128), color=(50, 150, 200))
    im2.save(FIXTURE_DIR / "images" / "train" / "garbage_sample02.png")
    with open(FIXTURE_DIR / "labels" / "train" / "garbage_sample02.txt", "w") as f:
        f.write("0 0.60 0.40 0.25 0.35\n")

    # val
    im3 = Image.new("RGB", (128, 128), color=(100, 200, 100))
    im3.save(FIXTURE_DIR / "images" / "val" / "dumping_sample03.jpg")
    with open(FIXTURE_DIR / "labels" / "val" / "dumping_sample03.txt", "w") as f:
        f.write("1 0.45 0.55 0.20 0.20\n")

    # test
    im4 = Image.new("RGB", (128, 128), color=(150, 50, 150))
    im4.save(FIXTURE_DIR / "images" / "test" / "road_sample04.webp")
    with open(FIXTURE_DIR / "labels" / "test" / "road_sample04.txt", "w") as f:
        f.write("2 0.70 0.30 0.10 0.15\n")

    print("Synthetic fixture generated at:", FIXTURE_DIR)


if __name__ == "__main__":
    build_synthetic_fixture()
