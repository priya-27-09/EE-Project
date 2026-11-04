import os
import json
import urllib.request
from PIL import Image
import io
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

def download_one(img_id, item, img_dir):
    img_info = item["img"]
    fname = f"taco_overflow_{img_id:04d}.jpg"
    out_path = os.path.join(img_dir, fname)
    
    if not os.path.exists(out_path):
        img_url = img_info.get("flickr_640_url") or img_info.get("flickr_url")
        if not img_url:
            return None
        try:
            req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw_bytes = resp.read()
                im = Image.open(io.BytesIO(raw_bytes))
                im.verify()
                with open(out_path, "wb") as f_out:
                    f_out.write(raw_bytes)
        except Exception as e:
            return None
            
    try:
        with Image.open(out_path) as im:
            real_w, real_h = im.size
    except Exception:
        return None
        
    img_copy = dict(img_info)
    img_copy["file_name"] = fname
    img_copy["width"] = real_w
    img_copy["height"] = real_h
    
    scale_x = real_w / float(img_info["width"])
    scale_y = real_h / float(img_info["height"])
    
    scaled_anns = []
    for a in item["anns"]:
        a_copy = dict(a)
        bx, by, bw, bh = a["bbox"]
        a_copy["bbox"] = [bx * scale_x, by * scale_y, bw * scale_x, bh * scale_y]
        scaled_anns.append(a_copy)
        
    return img_copy, scaled_anns

def download_taco():
    raw_dir = "dataset/expansion/raw/taco"
    os.makedirs(raw_dir, exist_ok=True)
    ann_path = os.path.join(raw_dir, "annotations.json")
    
    if not os.path.exists(ann_path):
        print("Fetching TACO annotations.json...")
        url = "https://raw.githubusercontent.com/pedropro/TACO/master/data/annotations.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            with open(ann_path, "wb") as f:
                f.write(data)
        print("Saved annotations.json")

    with open(ann_path, "r", encoding="utf-8") as f:
        coco = json.load(f)

    img_anns = {}
    for a in coco["annotations"]:
        img_id = a["image_id"]
        img_anns.setdefault(img_id, []).append(a)

    images_by_id = {img["id"]: img for img in coco["images"]}
    
    selected_images = {}
    for img_id, anns in img_anns.items():
        has_garbage_bag = any(a["category_id"] == 38 for a in anns)
        has_unlabeled = any(a["category_id"] == 58 for a in anns)
        has_cluster = len(anns) >= 3
        
        if has_garbage_bag or has_unlabeled or has_cluster:
            selected_images[img_id] = {
                "img": images_by_id[img_id],
                "anns": anns,
                "reason": "garbage_bag" if has_garbage_bag else ("unlabeled" if has_unlabeled else "litter_cluster")
            }

    print(f"Total candidate garbage overflow images in TACO: {len(selected_images)}")
    
    random.seed(42)
    selected_ids = sorted(list(selected_images.keys()))
    random.shuffle(selected_ids)
    selected_ids = selected_ids[:70]
    
    print(f"Downloading {len(selected_ids)} selected TACO images for Garbage Overflow using thread pool...")
    img_dir = os.path.join(raw_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    
    selected_coco_subset = {
        "images": [],
        "annotations": [],
        "categories": coco["categories"]
    }
    
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(download_one, img_id, selected_images[img_id], img_dir): img_id for img_id in selected_ids}
        for f in as_completed(futures):
            res = f.result()
            if res:
                img_copy, scaled_anns = res
                selected_coco_subset["images"].append(img_copy)
                selected_coco_subset["annotations"].extend(scaled_anns)
                
    subset_json_path = os.path.join(raw_dir, "taco_overflow_annotations.json")
    with open(subset_json_path, "w", encoding="utf-8") as f:
        json.dump(selected_coco_subset, f, indent=2)
        
    print(f"TACO download complete: {len(selected_coco_subset['images'])} images saved, {len(selected_coco_subset['annotations'])} annotations saved to {subset_json_path}")

if __name__ == "__main__":
    download_taco()
