#!/usr/bin/env python3
import os
import sys
import json
import re
import copy
from pathlib import Path
from typing import Any

# --- Import PyYAML ---
try:
    import yaml
except ImportError:
    yaml = None

# --- Helper Functions ---

def _is_int_str(s: str) -> bool:
    return re.fullmatch(r'\d+', (s or '')) is not None

def load_spec_file(path: str):
    """Smart loader: Loads JSON or YAML based on file extension."""
    path_obj = Path(path)
    if not path_obj.exists():
        # Fallback: if file missing, return empty dict (treats as new file)
        # print(f"Warning: File not found at {path}. Treating as empty.", file=sys.stderr)
        return {}

    try:
        if path_obj.suffix.lower() in ['.yaml', '.yml']:
            if yaml is None:
                print(f"Error: Cannot load {path}. PyYAML missing.", file=sys.stderr)
                sys.exit(1)
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        else:
            with open(path, 'r', encoding='utf-8-sig') as f:
                return json.load(f) or {}
    except Exception as e:
        print(f"Error: Could not parse file {path}. Reason: {e}", file=sys.stderr)
        return {}

def save_yaml(obj, path: str):
    if yaml:
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(obj, f, sort_keys=False, allow_unicode=True)
    else:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)

# --- Core Logic Functions ---

def load_baseline_operations(baseline_path: Path) -> set:
    print(f"\n=== LOADING BASELINE (Legacy APIs) ===")
    print(f"Baseline file: {baseline_path}")
    baseline_spec = load_spec_file(str(baseline_path))
    legacy_ops = set()
    
    if baseline_spec and "paths" in baseline_spec:
        for path_string, path_item in baseline_spec["paths"].items():
            if not isinstance(path_item, dict): continue
            for method in path_item.keys():
                if method.lower() in {"get", "put", "post", "delete", "patch", "options", "head", "trace"}:
                    op_key = f"{method.upper()}@{path_string}"
                    legacy_ops.add(op_key)
                    print(f"   Legacy: {op_key}")
    
    print(f"✅ Loaded {len(legacy_ops)} legacy operations from baseline.\n")
    return legacy_ops

def get_key_from_loc(loc_str: str) -> str:
    if loc_str and loc_str.startswith("paths."):
        tokens = loc_str.split('.')
        if len(tokens) >= 3:
            path_string = tokens[1]
            method = tokens[2].upper()
            return f"{method}@{path_string}"
        elif len(tokens) == 2:
            path_string = tokens[1]
            return f"PATH_ONLY@{path_string}"
    return None

def copy_operation_from_dest(new_spec: dict, dest_spec: dict, op_key: str):
    """Copies full operation from Head spec to Partial spec."""
    if not op_key or '@' not in op_key: return
    method, path = op_key.split('@', 1)
    method = method.lower()

    if "paths" not in new_spec: new_spec["paths"] = {}
    if path not in new_spec["paths"]: new_spec["paths"][path] = {}

    dest_paths = dest_spec.get("paths", {})
    if path in dest_paths and method in dest_paths[path]:
        new_spec["paths"][path][method] = copy.deepcopy(dest_paths[path][method])
        # print(f"   -> Copied full operation {method.upper()} {path}")

def detect_manual_changes(source_spec: dict, dest_spec: dict, affected_ops: set):
    """
    Manually compares Source (Main) vs Destination (Head) specs to find changes 
    that openapi-diff might ignore (like description/summary changes).
    """
    print("\n=== DEEP COMPARISON: Scanning all operations ===")
    
    dest_paths = dest_spec.get("paths") or {}
    source_paths = source_spec.get("paths") or {}
    
    op_methods = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}
    
    new_ops_count = 0
    modified_ops_count = 0

    for path, path_item in dest_paths.items():
        if not isinstance(path_item, dict): continue
        
        for method, op in path_item.items():
            if method.lower() not in op_methods: continue
            
            op_key = f"{method.upper()}@{path}"
            
            # 1. Check if New Operation (Not in Source)
            if path not in source_paths or method not in source_paths[path]:
                if op_key not in affected_ops:
                    print(f"   Detected NEW operation: {op_key}")
                    new_ops_count += 1
                affected_ops.add(op_key)
                continue
            
            # 2. Check if Modified (Compare Dicts)
            source_op = source_paths[path][method]
            
            # Convert to JSON string for stable comparison.
            # This catches descriptions, summaries, examples - EVERYTHING.
            if json.dumps(op, sort_keys=True) != json.dumps(source_op, sort_keys=True):
                if op_key not in affected_ops:
                    print(f"   Detected MODIFIED operation: {op_key}")
                    modified_ops_count += 1
                affected_ops.add(op_key)
    
    print(f"Deep comparison found: {new_ops_count} new + {modified_ops_count} modified operations")

def build_new_spec(diff: Any, legacy_ops: set, dest_spec: dict, source_spec: dict):
    new_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Changed-Only API Spec", "version": "1.0.0"},
        "paths": {}
    }
    
    affected_ops = set()

    # 1. Trust the Diff Tool (Fast, finds logic changes)
    items = []
    if isinstance(diff, dict):
        for b in ('breakingDifferences', 'nonBreakingDifferences', 'unclassifiedDifferences'):
            arr = diff.get(b)
            if isinstance(arr, list): items.extend(arr)
        if not items and 'differences' in diff: items = diff['differences']
    elif isinstance(diff, list): items = diff
    
    for it in items:
        loc_str = None
        if "destinationSpecEntityDetails" in it and it["destinationSpecEntityDetails"]:
            loc_str = (it["destinationSpecEntityDetails"][0] or {}).get('location')
        if not loc_str and "sourceSpecEntityDetails" in it and it["sourceSpecEntityDetails"]:
            loc_str = (it["sourceSpecEntityDetails"][0] or {}).get('location')

        if not loc_str: continue
        key = get_key_from_loc(loc_str)
        if key: affected_ops.add(key)

    # 2. Trust our Manual Deep Compare (Catches description/cosmetic changes)
    detect_manual_changes(source_spec, dest_spec, affected_ops)

    print(f"\n=== GOVERNANCE DECISION SUMMARY ===")
    print(f"Total affected operations (Diff + Deep Compare): {len(affected_ops)}")
    print(f"Legacy operations in baseline: {len(legacy_ops)}\n")
    
    included_ops = []
    ignored_ops = []
    
    for key in sorted(affected_ops):
        if key.startswith("PATH_ONLY@"):
            path_only = key.split('@')[1]
            is_legacy = any(op.endswith(f"@{path_only}") for op in legacy_ops)
            if is_legacy:
                ignored_ops.append(f"PATH {path_only} (legacy path)")
                print(f"❌ IGNORE: PATH {path_only} - Legacy path detected")
            else:
                included_ops.append(f"PATH {path_only} (new path)")
                print(f"✅ INCLUDE: PATH {path_only} - New path")
                if path_only in dest_spec.get("paths", {}):
                    new_spec["paths"][path_only] = copy.deepcopy(dest_spec["paths"][path_only])
        else:
            if key in legacy_ops:
                ignored_ops.append(f"{key} (legacy operation modified)")
                print(f"❌ IGNORE: {key} - Legacy operation (in baseline)")
            else:
                # Determine if it's a new method on existing path or completely new
                method, path = key.split('@', 1)
                is_new_method_on_legacy_path = any(op.endswith(f"@{path}") for op in legacy_ops)
                
                if is_new_method_on_legacy_path:
                    included_ops.append(f"{key} (new method on legacy path)")
                    print(f"✅ INCLUDE: {key} - New method on legacy path")
                else:
                    included_ops.append(f"{key} (modern/new operation)")
                    print(f"✅ INCLUDE: {key} - Modern or new operation")
                
                copy_operation_from_dest(new_spec, dest_spec, key)
    
    print(f"\n=== FINAL COUNTS ===")
    print(f"✅ Included: {len(included_ops)} operations")
    print(f"❌ Ignored: {len(ignored_ops)} operations")

    return new_spec

def find_all_refs(obj: Any, found_refs_set: set):
    if isinstance(obj, dict):
        if "$ref" in obj and isinstance(obj["$ref"], str): found_refs_set.add(obj["$ref"])
        for value in obj.values(): find_all_refs(value, found_refs_set)
    elif isinstance(obj, list):
        for item in obj: find_all_refs(item, found_refs_set)

def build_required_components(new_spec: dict, base_spec: dict):
    if "components" not in base_spec:
        new_spec["components"] = {}
        return

    if "components" not in new_spec:
        new_spec["components"] = {}

    refs_to_scan_queue = set()
    find_all_refs(new_spec.get("paths", {}), refs_to_scan_queue)
    scanned_refs = set()

    while refs_to_scan_queue:
        ref_str = refs_to_scan_queue.pop()
        if ref_str in scanned_refs: continue
        scanned_refs.add(ref_str)

        if not ref_str.startswith("#/components/"): continue
        
        parts = ref_str.split('/')
        if len(parts) < 4: continue
        
        comp_type = parts[2]
        comp_name = parts[3]
        
        base_comps = base_spec.get("components", {})
        if comp_type not in base_comps: continue
        
        if comp_name not in base_comps[comp_type]:
            # print(f"Warning: Reference {ref_str} not found in base spec.")
            continue

        if comp_type not in new_spec["components"]:
            new_spec["components"][comp_type] = {}

        if comp_name not in new_spec["components"][comp_type]:
            comp_def = base_comps[comp_type][comp_name]
            new_spec["components"][comp_type][comp_name] = copy.deepcopy(comp_def)
            find_all_refs(comp_def, refs_to_scan_queue)

    count = 0
    for key, val in new_spec.get("components", {}).items():
        count += len(val)
    print(f"Pruned components. Kept {count} total referenced components.")

# --- Main Execution Block ---

def main():
    # 1. Determine Paths (GitHub Actions Standard)
    current_dir = Path(".")
    artifact_dir = current_dir
    pipeline_workspace = current_dir # In GitHub, workspace is often just root

    # Arguments: python script.py [baseline_filename]
    baseline_filename = "swagger_baseline.json"
    if len(sys.argv) > 1:
        baseline_filename = sys.argv[1]
    
    # Locate files in root (standard for your GitHub workflow)
    baseline_path = pipeline_workspace / baseline_filename
    diff_path = artifact_dir / "diff.json"
    out_json = artifact_dir / "partial_spec.json"
    out_yaml = artifact_dir / "partial_spec.yaml"
    
    def get_existing_path(base_name_no_ext):
        p_yaml = artifact_dir / f"{base_name_no_ext}.yaml"
        p_json = artifact_dir / f"{base_name_no_ext}.json"
        if p_yaml.exists(): return p_yaml
        if p_json.exists(): return p_json
        return p_json

    # Look for files generated by your workflow steps
    main_spec_path = get_existing_path("swagger_main")
    head_spec_path = get_existing_path("swagger_head")

    print(f"Baseline: {baseline_path}")
    print(f"Head Spec: {head_spec_path}")

    # 2. Load Diff (Optimistic)
    diff_data = {}
    if diff_path.exists() and diff_path.stat().st_size > 0:
        txt = diff_path.read_text(encoding='utf-8-sig').strip()
        if txt:
            try:
                diff_data = json.loads(txt[txt.find('{'):]) if '{' in txt else {}
            except:
                print("Warning: Failed to parse diff.json. Will rely on manual comparison.")

    # 3. Load Specs
    legacy_ops = load_baseline_operations(baseline_path)
    dest_spec = load_spec_file(str(head_spec_path))
    source_spec = load_spec_file(str(main_spec_path)) # Needed for manual compare

    if not dest_spec:
        print(f"Error: Could not load head spec.", file=sys.stderr)
        sys.exit(1)

    # 4. Run Logic
    print("\n" + "="*60)
    print("STEP 1: DETECTING CHANGES (Diff + Deep Compare)")
    print("="*60)
    
    # We pass 'source_spec' here to enable manual deep comparison
    new_spec = build_new_spec(diff_data, legacy_ops, dest_spec, source_spec)

    print("\n" + "="*60)
    print("STEP 2: BUILDING MINIMAL COMPONENTS")
    print("="*60)
    build_required_components(new_spec, base_spec=dest_spec)

    # 5. Save
    print("\n" + "="*60)
    print("STEP 3: SAVING FINAL PARTIAL SPEC")
    print("="*60)
    out_json.write_text(json.dumps(new_spec, indent=2, ensure_ascii=False), encoding='utf-8')
    save_yaml(new_spec, str(out_yaml))
    
    # Print final statistics
    total_paths = len(new_spec.get("paths", {}))
    total_operations = sum(
        len([m for m in methods.keys() if m.lower() in {"get", "put", "post", "delete", "patch", "options", "head", "trace"}])
        for methods in new_spec.get("paths", {}).values()
        if isinstance(methods, dict)
    )
    
    print(f"\n✅ SUCCESS!")
    print(f"   Output: {out_json}")
    print(f"   Paths: {total_paths}")
    print(f"   Operations: {total_operations}")
    print("="*60 + "\n")
    sys.exit(0)

if __name__ == "__main__":
    main()