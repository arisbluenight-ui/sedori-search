import base64, hashlib, json, re, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
import anthropic

USE_IMAGE_CACHE = False
IMG_CACHE_DIR   = Path("image_cache")
PARSE_FAIL_LOG  = Path("vision_parse_failures.jsonl")

VISION_TARGET_BRANDS = {
    "LOEWE", "PRADA", "GUCCI", "CELINE",
    "FENDI", "BURBERRY", "MIU MIU", "GIVENCHY",
    "SOMES", "IACUCCI", "BONAVENTURA", "PIERRE HARDY",
    "3.1 PHILLIP LIM", "GLENROYAL", "MYSTERY RANCH",
    "TOM FORD", "SOEUR", "万双",
    "A VACATION", "MOTHERHOUSE", "LAST CROPS",
    "ペッレモルビダ", "PELLE MORBIDA",
}

MAX_SOLD_COMPARE   = 5
MAX_IMGS_PER_ITEM  = 3
CONF_CONFIRMED     = 0.7
CONF_NEAR          = 0.5

VISION_CSV_COLUMNS = [
    "sold_count_vision_confirmed",
    "sold_count_near_variant",
    "vision_reject_count",
    "model_match_confidence",
    "attribute_conflict_flags",
    "manual_review_required",
    "vision_top_match_url",
    "vision_reason_summary",
]

VISION_PROMPT = """
あなたはブランドバッグの専門鑑定士です。
画像セットA（仕入れ候補）と画像セットB（メルカリSOLD商品）を比較し、同一モデルかどうかを判定してください。

確認要素：
1. バッグの基本形状・シルエット
2. ハンドル・ストラップの形状と取付位置
3. 開口部の構造（ファスナー・フラップ・巾着など）
4. 金具の形状・色・位置
5. ロゴの位置・形式
6. ポケットの有無と位置
7. 色
8. サイズ感（参考程度）

必ずJSONのみを返してください（前置き・後置き不要）：
{
  "verdict": "same_model" または "near_variant" または "different_model",
  "confidence": 0.0から1.0,
  "color_match": true または false,
  "shape_match": true または false,
  "hardware_match": true または false,
  "handle_match": true または false,
  "logo_match": true または false,
  "conflict_flags": ["不一致点（日本語）"],
  "match_points": ["一致点（日本語）"],
  "reason_summary": "30字以内の日本語サマリ"
}

same_model: 同一モデル（confidence 0.7以上推奨）
near_variant: 同系列・異なるサイズや仕様の可能性
different_model: 別モデル
"""

_SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

def _media_type(url, ct):
    ct = ct.lower()
    if "webp" in ct: return "image/webp"
    if "png"  in ct: return "image/png"
    if "gif"  in ct: return "image/gif"
    if "svg"  in ct: return None  # SVG 非対応
    u = url.lower().split("?")[0]
    if u.endswith(".webp"): return "image/webp"
    if u.endswith(".png"):  return "image/png"
    if u.endswith(".svg"):  return None  # SVG 非対応
    return "image/jpeg"

def _check_magic_bytes(raw: bytes) -> bool:
    """先頭バイトを見て Anthropic API が受け付けるフォーマットか確認する。"""
    if raw[:2] == b"\xff\xd8":                    return True   # JPEG
    if raw[:8] == b"\x89PNG\r\n\x1a\n":           return True   # PNG
    if raw[:6] in (b"GIF87a", b"GIF89a"):         return True   # GIF
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP": return True # WebP
    return False  # AVIF / SVG / その他

def fetch_image(url):
    if USE_IMAGE_CACHE:
        IMG_CACHE_DIR.mkdir(exist_ok=True)
        key  = hashlib.md5(url.encode()).hexdigest()
        meta = IMG_CACHE_DIR / f"{key}.json"
        data = IMG_CACHE_DIR / f"{key}.b64"
        if meta.exists() and data.exists():
            return data.read_text(), json.loads(meta.read_text())["media_type"]
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as r:
            ct  = r.headers.get("Content-Type", "image/jpeg")
            mt  = _media_type(url, ct)
            if mt is None:
                return None, None  # SVG など非対応フォーマット
            raw = r.read()
            if not _check_magic_bytes(raw):
                return None, None  # AVIF など実バイナリが非対応
            b64 = base64.standard_b64encode(raw).decode()
            if USE_IMAGE_CACHE:
                data.write_text(b64)
                meta.write_text(json.dumps({"url": url, "media_type": mt}))
            return b64, mt
    except Exception:
        return None, None

def build_blocks(image_urls, label):
    blocks = [{"type": "text", "text": f"【{label}】"}]
    loaded = 0
    for url in image_urls:
        if loaded >= MAX_IMGS_PER_ITEM: break
        b64, mt = fetch_image(url)
        if b64 is None: continue
        blocks.append({"type":"image","source":{"type":"base64","media_type":mt,"data":b64}})
        loaded += 1
    return blocks if loaded > 0 else []

def _parse(raw, ctx=""):
    cleaned = re.sub(r"```json\s*","",raw)
    cleaned = re.sub(r"```\s*","",cleaned).strip()
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m: cleaned = m.group(0)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        with open(PARSE_FAIL_LOG,"a",encoding="utf-8") as f:
            f.write(json.dumps({"ctx":ctx,"raw":raw[:400],"err":str(e),
                                "ts":time.strftime("%Y-%m-%d %H:%M:%S")},
                               ensure_ascii=False)+"\n")
        return None

def _call_api(blocks, brand, hint, retries=2):
    client = anthropic.Anthropic()
    prompt = {"type":"text","text":f"ブランド: {brand}  モデルヒント: {hint}\n\n{VISION_PROMPT}"}
    msgs = [{"role":"user","content": blocks + [prompt]}]
    for attempt in range(retries + 1):
        try:
            r = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=600,
                messages=msgs
            )
            result = _parse(r.content[0].text, ctx=f"{brand}/{hint}/attempt{attempt}")
            if result: return result
        except Exception as e:
            time.sleep(1.5)
            import logging as _log
            _log.warning("Vision API エラー (attempt %d): %s: %s", attempt, type(e).__name__, str(e)[:200])
        if attempt < retries: time.sleep(1.5)
    return None

def _need_review(confirmed, near, rejected, top_conf):
    total = confirmed + near + rejected
    if total == 0:                               return True
    if confirmed == 0 and near == 0:             return True
    if confirmed == 0 and top_conf < CONF_NEAR:  return True
    if rejected == total:                         return True
    return False

def vision_compare_sold_items(source_item, mercari_sold_items, brand, model_hint=""):
    out = {
        "sold_count_vision_confirmed": 0,
        "sold_count_near_variant":     0,
        "vision_reject_count":         0,
        "model_match_confidence":      0.0,
        "attribute_conflict_flags":    "",
        "manual_review_required":      False,
        "vision_top_match_url":        "",
        "vision_reason_summary":       "",
        "vision_details":              [],
    }
    src_blocks = build_blocks(source_item.get("image_urls", []), "画像セットA（仕入れ候補）")
    if not src_blocks:
        out["manual_review_required"] = True
        out["vision_reason_summary"]  = "仕入れ画像取得失敗"
        return out

    all_flags           = set()
    top_confirmed_conf  = 0.0
    top_url             = ""
    top_reason          = ""
    fallback_top_conf   = 0.0
    fallback_top_url    = ""
    fallback_top_reason = ""

    for sold in mercari_sold_items[:MAX_SOLD_COMPARE]:
        sold_blocks = build_blocks(sold.get("image_urls", []), "画像セットB（メルカリSOLD）")
        if not sold_blocks:
            out["vision_details"].append({"item_url": sold.get("item_url",""), "verdict": "skip", "reason": "sold画像取得失敗"})
            continue

        j = _call_api(src_blocks + sold_blocks, brand, model_hint)
        if j is None:
            out["manual_review_required"] = True
            out["vision_details"].append({"item_url": sold.get("item_url",""), "verdict": "parse_error", "reason": "パース失敗"})
            continue

        verdict = j.get("verdict","different_model")
        conf    = float(j.get("confidence", 0.0))
        reason  = j.get("reason_summary","")

        if verdict == "same_model" and conf >= CONF_CONFIRMED:
            out["sold_count_vision_confirmed"] += 1
            # confirmed の中で最高 conf を保持
            if conf > top_confirmed_conf:
                top_confirmed_conf = conf
                top_url    = sold.get("item_url","")
                top_reason = reason
        elif verdict == "near_variant":
            out["sold_count_near_variant"] += 1
        elif verdict == "same_model":
            out["sold_count_near_variant"] += 1
        else:
            out["vision_reject_count"] += 1

        # fallback: 全体の最高 conf（manual_review_required 判定用）
        if conf > fallback_top_conf:
            fallback_top_conf   = conf
            fallback_top_url    = sold.get("item_url","")
            fallback_top_reason = reason

        for flag in j.get("conflict_flags", []): all_flags.add(flag)

        out["vision_details"].append({
            "item_url": sold.get("item_url",""), "title": sold.get("title",""),
            "verdict": verdict, "confidence": conf,
            "confirmed": verdict=="same_model" and conf >= CONF_CONFIRMED,
            "color_match": j.get("color_match"), "shape_match": j.get("shape_match"),
            "hardware_match": j.get("hardware_match"), "handle_match": j.get("handle_match"),
            "conflict_flags": j.get("conflict_flags",[]), "match_points": j.get("match_points",[]),
            "reason": reason,
        })
        time.sleep(0.5)

    # confirmed が1件以上あれば confirmed 側の url/reason を使い、なければ fallback
    if out["sold_count_vision_confirmed"] >= 1:
        out["vision_top_match_url"]   = top_url
        out["vision_reason_summary"]  = top_reason
    else:
        out["vision_top_match_url"]   = fallback_top_url
        out["vision_reason_summary"]  = fallback_top_reason

    out["model_match_confidence"]   = round(fallback_top_conf, 2)
    out["attribute_conflict_flags"] = "／".join(sorted(all_flags))

    if not out["manual_review_required"]:
        out["manual_review_required"] = _need_review(
            out["sold_count_vision_confirmed"],
            out["sold_count_near_variant"],
            out["vision_reject_count"],
            fallback_top_conf,
        )
    return out
