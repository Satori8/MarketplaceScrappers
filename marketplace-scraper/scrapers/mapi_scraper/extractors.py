import json
import re
from typing import Dict, List, Optional

def _extract_ld_json(html: str) -> List[Dict]:
    """Extract all application/ld+json script blocks from HTML and parse them."""
    results = []
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    for block in blocks:
        try:
            results.append(json.loads(block.strip()))
        except:
            pass
    return results

def _extract_js_assignment_raw(html: str, var_name: str) -> Optional[str]:
    """Extract the value part of a JS variable assignment like `window.VarName = ...`."""
    pattern = re.escape(var_name) + r'\s*=\s*'
    m = re.search(pattern, html)
    if not m:
        return None
    
    start_pos = m.end()
    text = html[start_pos:].strip()
    if not text:
        return None

    # Check if it starts with { or [ or (
    if text.startswith('{') or text.startswith('[') or text.startswith('('):
        open_char = text[0]
        close_char = '}' if open_char == '{' else (']' if open_char == '[' else ')')
        depth = 0
        in_string = False
        escape = False
        quote_char = None
        
        for i, ch in enumerate(text):
            if not in_string:
                if ch == open_char:
                    depth += 1
                elif ch == close_char:
                    depth -= 1
                    if depth == 0:
                        return text[:i+1]
                elif ch in ['"', "'", "`"]:
                    in_string = True
                    quote_char = ch
            else:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == quote_char:
                    in_string = False
        
    # Fallback for simple values (numbers, plain identifiers)
    # look for semicolon or </script>
    m_end = re.search(r';(?!<)|</script>', text)
    if m_end:
        return text[:m_end.start()].strip()
        
    return text.strip()

def _extract_json_assignment(html: str, var_name: str) -> Optional[Dict]:
    """Extract and parse a JS variable assignment as JSON."""
    raw = _extract_js_assignment_raw(html, var_name)
    if raw:
        try:
            return json.loads(raw)
        except:
            pass
    return None

def _extract_script_by_id(html: str, script_id: str) -> Optional[str]:
    m = re.search(
        r'<script[^>]*\bid=["\']' + re.escape(script_id) + r'["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return None
    return m.group(1).strip()

def _decode_rz_dt_string(s: str) -> str:
    token = s.strip()
    if token.startswith("G"):
        token = token[1:]

    token = (
        token.replace("$dt$", ".")
        .replace("$sh$", "/")
        .replace("$qr$", "?")
        .replace("$am$", "&")
        .replace("$ad$", "&") # Common in rz-client-state for query join
        .replace("$eq$", "=")
        .replace("$cl$", ":")
        .replace("$pc$", "%")
    )

    if token.startswith("http"):
        return token

    if token.startswith("."):
        token = token[1:]

    if "common-api.rozetka.com.ua" in token:
        prefix = "https://" if not token.startswith("https://") else ""
        return prefix + token
    
    if "common-api.rozetka" in token:
        token = token.replace("common-api.rozetka", "common-api.rozetka.com.ua")
        prefix = "https://" if not token.startswith("https://") else ""
        return prefix + token
    if token.startswith("http://") or token.startswith("https://"):
        return token
    if token.startswith("common-api") or token.startswith("rozetka"):
        return "https://" + token
    return token

def _find_common_api_request_in_client_state(client_state_text: str) -> Optional[str]:
    marker = "G$dt$common-api"
    # Find all occurrences
    matches = []
    for m in re.finditer(re.escape(marker), client_state_text):
        idx = m.start()
        end = idx
        while end < len(client_state_text):
            ch = client_state_text[end]
            if ch in ['"', "'", "\\", " ", "\n", "\r", "\t", "<", ">"]:
                break
            end += 1
        matches.append(client_state_text[idx:end])
    
    # Also look for raw URLs
    raw_urls = re.findall(r'https?://common-api\.rozetka\.com\.ua[^\s"\'<>]+', client_state_text)
    
    all_candidates = []
    for m in matches:
        all_candidates.append(_decode_rz_dt_string(m))
    for u in raw_urls:
        all_candidates.append(u)
    
    # Priority list (Ordered from most desirable to least)
    priority_keywords = ["product/details", "goods/get-details", "catalog/search/v4", "catalog/search"]
    
    # Sort candidates by length (longer URLs usually have more filters/IDs)
    all_candidates.sort(key=len, reverse=True)

    for kw in priority_keywords:
        for url in all_candidates:
            if kw in url and "top-phrases" not in url and "banners" not in url:
                return url
                
    # Fallback to anything else that's not top-phrases/banners
    for url in all_candidates:
        if "top-phrases" not in url and "banners" not in url:
            return url

    if all_candidates:
        return all_candidates[0]
        
    return None
