#!/usr/bin/env python3
import os
import sys
import json
import re
import copy
from pathlib import Path
from typing import Any

# --- Try to import YAML, but it's not critical ---
try:
    import yaml
except Exception:
    yaml = None

# --- Helper Functions ---

def _is_int_str(s: str) -> bool:
    return re.fullmatch(r'\d+', (s or '')) is not None

def load_json(path: str):
    """Loads a JSON file from the given string path."""
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {path}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {path}", file=sys.stderr)
        return None

def save_yaml(obj, path: str):
    """Saves an object to a YAML file, or falls back to JSON."""
    if yaml:
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(obj, f, sort_keys=False, allow_unicode=True)
    else:
        # Fallback to JSON if YAML not installed
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)

def loc_to_tokens(loc: str):
    if loc is None:
        return []
    return loc.split('.')

def set_by_tokens(doc, tokens, value):
    if not tokens:
        raise ValueError('Empty token list')
    cur = doc
    for i, tok in enumerate(tokens):
        last = (i == len(tokens) - 1)
        if isinstance(cur, list) and _is_int_str(tok):
            idx = int(tok)
            if last:
                if idx < len(cur):
                    cur[idx] = value
                else:
                    while len(cur) < idx:
                        cur.append(None)
                    cur.append(value)
                return
            if idx < len(cur):
                if cur[idx] is None:
                    next_tok = tokens[i+1] if i+1 < len(tokens) else None
                    cur[idx] = [] if _is_int_str(next_tok) else {}
                cur = cur[idx]
            else:
                while len(cur) <= idx:
                    cur.append({})
                cur = cur[idx]
            continue
        if not isinstance(cur, dict):
            cur = {}
        if last:
            cur[tok] = value
            return
        next_tok = tokens[i+1] if i+1 < len(tokens) else None
        if tok not in cur or cur[tok] is None:
            cur[tok] = [] if _is_int_str(next_tok) else {}
        cur = cur[tok]

def remove_by_tokens(doc, tokens):
    if not tokens:
        raise ValueError('Refusing to remove whole document')
    cur = doc
    for tok in tokens[:-1]:
        if isinstance(cur, dict):
            cur = cur.get(tok)
        elif isinstance(cur, list) and _is_int_str(tok):
            idx = int(tok)
            if 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return
        else:
            return
        if cur is None:
            return
    last = tokens[-1]
    if isinstance(cur, dict):
        cur.pop(last, None)
    elif isinstance(cur, list) and _is_int_str(last):
        idx = int(last)
        if 0 <= idx < len(cur):
            cur.pop(idx)

def mark_removed_by_tokens(doc, tokens):
    set_by_tokens(doc, tokens, {"x-removed": True})

def apply_diff_item_robust(new_spec: dict, item: dict, remove_actually: bool = False):
    action = item.get('action')
    def _get_loc(det):
        return (det or {}).get('location') or (det or {}).get('pointer')
    if action in ('add', 'change'):
        for det in item.get('destinationSpecEntityDetails', []) or []:
            loc = _get_loc(det)
            val = det.get('value')
            if not loc or val is None:
                continue
            tokens = loc_to_tokens(loc)
            set_by_tokens(new_spec, tokens, val)
    elif action == 'remove':
        for det in item.get('sourceSpecEntityDetails', []) or []:
            loc = _get_loc(det)
            if not loc:
                continue
            tokens = loc_to_tokens(loc)
            if remove_actually:
                remove_by_tokens(new_spec, tokens)
            else:
                mark_removed_by_tokens(new_spec, tokens)
    else:
        for det in item.get('destinationSpecEntityDetails', []) or []:
            loc = _get_loc(det)
            val = det.get('value')
            if loc and val is not None:
                set_by_tokens(new_spec, loc_to_tokens(loc), val)

# --- Core Logic Functions ---

def load_baseline_operations(pipeline_workspace: Path) -> set:
    """
    Loads the baseline spec and returns a set of all defined API operations
    in the format 'METHOD@/path/string' (e.g., 'GET@/v1/members-info/{id}').
    """
    baseline_path = pipeline_workspace / "swagger_baseline.json"
    print(f"Loading legacy baseline from: {baseline_path}")
    
    baseline_spec = load_json(str(baseline_path))
    legacy_ops = set()
    
    if baseline_spec and "paths" in baseline_spec:
        for path_string, path_item in baseline_spec["paths"].items():
            if not isinstance(path_item, dict):
                continue
            for method in path_item.keys():
                if method.lower() in {"get", "put", "post", "delete", "patch", "options", "head", "trace"}:
                    op_key = f"{method.upper()}@{path_string}"
                    legacy_ops.add(op_key)
        
        print(f"Loaded {len(legacy_ops)} legacy operations from baseline.")
        return legacy_ops
    
    print("Warning: No baseline spec found or baseline has no paths.")
    return set()

def get_key_from_loc(loc_str: str) -> str:
    """Converts a location string 'paths./v1.get' into an op_key 'GET@/v1'"""
    if loc_str and loc_str.startswith("paths."):
        tokens = loc_str.split('.')
        if len(tokens) >= 3: # paths./path.method
            path_string = tokens[1]
            method = tokens[2].upper()
            return f"{method}@{path_string}"
        elif len(tokens) == 2: # paths./path
            path_string = tokens[1]
            return f"PATH_ONLY@{path_string}"
    return None

def build_new_spec(diff: Any, legacy_ops: set, remove_actually: bool = False):
    """
    Builds a new spec containing only non-legacy paths from the diff.
    """
    new_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Changed-Only API Spec", "version": "1.0.0"},
        "paths": {}
    }
    items = []
    if isinstance(diff, dict):
        for b in ('breakingDifferences', 'nonBreakingDifferences', 'unclassifiedDifferences'):
            arr = diff.get(b)
            if isinstance(arr, list):
                items.extend(arr)
        if not items and 'differences' in diff and isinstance(diff.get('differences'), list):
            items = diff['differences']
    elif isinstance(diff, list):
        items = diff
    
    for it in items:
        action = it.get('action')
        loc_str = None
        key_to_check = None
        
        if action in ('add', 'change'):
            if "destinationSpecEntityDetails" in it and it["destinationSpecEntityDetails"]:
                loc_str = (it["destinationSpecEntityDetails"][0] or {}).get('location')
        elif action == 'remove':
            if "sourceSpecEntityDetails" in it and it["sourceSpecEntityDetails"]:
                loc_str = (it["sourceSpecEntityDetails"][0] or {}).get('location')
        
        if not loc_str:
            continue
        
        key_to_check = get_key_from_loc(loc_str)
        
        if not key_to_check:
            continue

        if key_to_check in legacy_ops:
            print(f"Ignoring change in legacy operation: {key_to_check}")
            continue
        elif key_to_check.startswith("PATH_ONLY@"):
            path_only = key_to_check.split('@')[1]
            is_legacy = any(op.endswith(f"@{path_only}") for op in legacy_ops)
            if is_legacy:
                print(f"Ignoring change in legacy path-level item: {path_only}")
                continue
            else:
                print(f"Including change in new path-level item: {path_only}")
        else:
             print(f"Including change in new operation: {key_to_check}")
        
        apply_diff_item_robust(new_spec, it, remove_actually=remove_actually)
    return new_spec

def sync_responses_from_base(new_spec: dict, source_spec: dict = None, dest_spec: dict = None):
    """
    Restores $ref-based schemas from the base spec to replace inline
    schemas that come from the diff tool.
    """
    base_spec = dest_spec or source_spec
    if not isinstance(base_spec, dict):
        print("No base spec available for syncing responses.")
        return

    base_paths = base_spec.get("paths") or {}
    op_methods = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}

    for path, path_item in (new_spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        base_path_item = base_paths.get(path)
        if not isinstance(base_path_item, dict):
            continue

        for method, op in path_item.items():
            if not isinstance(op, dict) or method.lower() not in op_methods:
                continue

            base_op = base_path_item.get(method)
            if isinstance(base_op, dict):
                # Sync Responses
                base_responses = base_op.get("responses")
                if isinstance(base_responses, dict) and base_responses:
                    op["responses"] = copy.deepcopy(base_responses)
                    print(f"Synced responses for {method.upper()} {path} from base spec.")
                
                # Sync RequestBody
                base_request_body = base_op.get("requestBody")
                if isinstance(base_request_body, dict) and base_request_body:
                    op["requestBody"] = copy.deepcopy(base_request_body)
                    print(f"Synced requestBody for {method.upper()} {path} from base spec.")


def ensure_operations_have_responses(spec: dict, dest_spec: dict = None, source_spec: dict = None):
    """Fallback to ensure all ops have at least a default response."""
    op_methods = {"get","put","post","delete","options","head","patch","trace"}
    for path, path_item in (spec.get('paths') or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, op in list(path_item.items()):
            if not isinstance(method, str):
                continue
            if method.lower() not in op_methods:
                continue
            if not isinstance(op, dict):
                continue
            responses = op.get('responses')
            if isinstance(responses, dict) and len(responses) > 0:
                continue
            
            copied = False
            for candidate in (dest_spec, source_spec):
                if not isinstance(candidate, dict):
                    continue
                cand_paths = candidate.get('paths') or {}
                if path in cand_paths and isinstance(cand_paths[path], dict):
                    cand_op = cand_paths[path].get(method)
                    if isinstance(cand_op, dict):
                        cand_responses = cand_op.get('responses')
                        if isinstance(cand_responses, dict) and len(cand_responses) > 0:
                            op['responses'] = copy.deepcopy(cand_responses)
                            copied = True
                            break
            if copied:
                continue
            
            op['responses'] = {
                "default": {
                    "description": "Default response"
                }
            }

def find_all_refs(obj: Any, found_refs_set: set):
    """Recursively finds all $ref values in a dict or list."""
    if isinstance(obj, dict):
        if "$ref" in obj and isinstance(obj["$ref"], str):
            found_refs_set.add(obj["$ref"])
        for value in obj.values():
            find_all_refs(value, found_refs_set)
    elif isinstance(obj, list):
        for item in obj:
            find_all_refs(item, found_refs_set)

def build_required_components(new_spec: dict, base_spec: dict):
    """
    Builds a new components block containing only schemas that are
    transitively referenced by the paths.
    """
    try:
        base_schemas = base_spec["components"]["schemas"]
    except (KeyError, TypeError, AttributeError):
        print("Warning: Base spec has no components/schemas to reference.")
        new_spec["components"] = {"schemas": {}}
        return

    refs_to_scan_queue = set()
    find_all_refs(new_spec.get("paths", {}), refs_to_scan_queue)

    final_schemas = {}
    scanned_refs = set()

    while refs_to_scan_queue:
        ref_str = refs_to_scan_queue.pop()
        
        if ref_str in scanned_refs:
            continue
        scanned_refs.add(ref_str)

        try:
            if not ref_str.startswith("#/components/schemas/"):
                continue
            comp_name = ref_str.split('/')[-1]
        except Exception:
            continue

        if comp_name not in final_schemas:
            if comp_name in base_schemas:
                schema_def = base_schemas[comp_name]
                final_schemas[comp_name] = schema_def
                find_all_refs(schema_def, refs_to_scan_queue)
            else:
                print(f"Warning: Could not find schema definition for {comp_name}")

    print(f"Pruned components. Kept {len(final_schemas)} referenced schemas.")
    new_spec["components"] = {"schemas": final_schemas}


# --- Main Execution Block ---

def main():
    # 1. Set up paths from environment variables
    artifact_dir_str = os.environ.get('BUILD_ARTIFACTSTAGINGDIRECTORY') or os.environ.get('BUILD_ARTIFACTSTAGINGDIRECTORY'.upper()) or r"."
    pipeline_workspace_str = os.environ.get('PIPELINE_WORKSPACE') or os.environ.get('PIPELINE_WORKSPACE'.upper()) or r"."

    artifact_dir = Path(artifact_dir_str)
    pipeline_workspace = Path(pipeline_workspace_str)

    diff_path = artifact_dir / "diff.json"
    out_json = artifact_dir / "partial_spec.json"
    out_yaml = artifact_dir / "partial_spec.yaml"
    main_spec_path = artifact_dir / "swagger_main.json"
    head_spec_path = artifact_dir / "swagger_head.json"

    print("Artifact staging directory:", artifact_dir_str)
    print("Pipeline workspace directory:", pipeline_workspace_str)
    print("Looking for diff file at:", str(diff_path))
    print("Baseline spec will be loaded from:", str(pipeline_workspace / "swagger_baseline.json"))

    # 2. Load Diff File
    if not diff_path.exists() or diff_path.stat().st_size == 0:
        print("No diff.json found or file is empty. Skipping partial spec generation.")
        sys.exit(0)

    txt = diff_path.read_text(encoding='utf-8-sig').strip()
    if not txt:
        print("diff.json is empty after reading. Exiting.")
        sys.exit(0)

    if txt.startswith("No changes found between the two specifications"):
        print("No API changes found — writing empty partial spec and exiting successfully.")
        empty_spec = {
            "openapi": "3.0.0",
            "info": {"title": "Changed-Only API Spec", "version": "1.0.0"},
            "paths": {},
            "components": {"schemas": {}}
        }
        out_json.write_text(json.dumps(empty_spec, indent=2, ensure_ascii=False), encoding='utf-8')
        save_yaml(empty_spec, str(out_yaml))
        print(f"Generated empty partial spec: {out_json}")
        sys.exit(0)
        
    def load_json_from_text(txt):
        if not txt:
            return {}
        i = txt.find('{')
        if i > 0:
            txt = txt[i:]
        return json.loads(txt)

    try:
        diff_data = load_json_from_text(txt)
    except Exception as e:
        print("Failed to parse diff.json:", e, file=sys.stderr)
        print("Raw diff content (first 400 chars):", file=sys.stderr)
        print(txt[:400], file=sys.stderr)
        sys.exit(1)

    # 3. Load all necessary specs
    legacy_ops = load_baseline_operations(pipeline_workspace)
    source_spec = load_json(str(main_spec_path)) # swagger_main.json
    dest_spec = load_json(str(head_spec_path))   # swagger_head.json

    if not dest_spec:
        print(f"Error: Could not load head spec from {head_spec_path}. Cannot continue.", file=sys.stderr)
        sys.exit(1)

    # 4. Run the script logic in the correct order
    print("Step 1: Building spec from diff and filtering legacy ops...")
    new_spec = build_new_spec(diff_data, legacy_ops=legacy_ops, remove_actually=False)

    print("Step 2: Syncing responses and requestBodies from head spec to restore $refs...")
    sync_responses_from_base(new_spec, source_spec=source_spec, dest_spec=dest_spec)

    print("Step 3: Ensuring all operations have a response block...")
    ensure_operations_have_responses(new_spec, dest_spec=dest_spec, source_spec=source_spec)

    print("Step 4: Building the minimal required components/schemas block...")
    build_required_components(new_spec, base_spec=dest_spec)

    # 5. Save the final, correct, and minimal spec
    print("Step 5: Saving final partial spec...")
    out_json.write_text(json.dumps(new_spec, indent=2, ensure_ascii=False), encoding='utf-8')
    save_yaml(new_spec, str(out_yaml))

    print(f"Partial spec saved: {out_json}")
    print(f"Partial spec (YAML) saved: {out_yaml}")
    sys.exit(0)

if __name__ == "__main__":
    main()