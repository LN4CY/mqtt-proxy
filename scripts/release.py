
#!/usr/bin/env python3
import sys
import re
import datetime
import subprocess
import argparse
import os

def run_command(command):
    print(f"Running: {command}")
    try:
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        sys.exit(1)

def update_readme(version):
    readme_path = "README.md"
    if not os.path.exists(readme_path):
        # Fallback for running from scripts dir
        readme_path = "../README.md"
        if not os.path.exists(readme_path):
            print("README.md not found!")
            sys.exit(1)

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update Version Line (e.g. "**Version**: 1.0.5")
    version_pattern = r"(\*\*Version\*\*: )(\d+\.\d+\.\d+)"
    if not re.search(version_pattern, content):
        print("Warning: Could not find '**Version**: ...' line in README.md. Skipping version update in file.")
    else:
        content = re.sub(version_pattern, f"\\1{version}", content)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"Updated README.md with version {version}")
    return readme_path

def update_version_py(version):
    version_path = "version.py"
    if not os.path.exists(version_path):
        version_path = "../version.py"
        if not os.path.exists(version_path):
            print("version.py not found!")
            sys.exit(1)
            
    with open(version_path, "r", encoding="utf-8") as f:
        content = f.read()

    version_pattern = r'(__version__\s*=\s*)(["\'])(.*?)(["\'])'
    new_content = re.sub(version_pattern, f'\\g<1>\\g<2>{version}\\g<4>', content)
    
    with open(version_path, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    print(f"Updated version.py with version {version}")
    return version_path

def extract_release_notes(version):
    notes_path = "RELEASE_NOTES.md"
    if not os.path.exists(notes_path):
        notes_path = "../RELEASE_NOTES.md"
        if not os.path.exists(notes_path):
            print("RELEASE_NOTES.md not found!")
            return None
            
    with open(notes_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    version_header = f"# Release v{version}"
    start_line = -1
    for i, line in enumerate(lines):
        if line.strip() == version_header:
            start_line = i
            break
            
    if start_line == -1:
        print(f"Warning: Could not find header '{version_header}' in RELEASE_NOTES.md")
        return None
        
    # Collect lines until the next version header or end of file
    release_notes = []
    for i in range(start_line + 1, len(lines)):
        if re.match(r'^#\s+Release\s+v[\d\.]+', lines[i].strip()):
            break
        if lines[i].strip() == '---' and i + 1 < len(lines) and re.match(r'^#\s+Release\s+v[\d\.]+', lines[i+1].strip()):
            continue
        release_notes.append(lines[i])
        
    # Trim leading/trailing whitespace lines
    notes_content = "".join(release_notes).strip()
    
    output_path = "latest_notes.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(notes_content)
        
    print(f"Extracted release notes for v{version} to {output_path}")
    return output_path

def git_commit_and_tag(version, files_to_commit):
    tag_name = f"v{version}"
    print(f"Creating git release for {tag_name}...")
    
    # Add changed files
    for file_path in files_to_commit:
        run_command(f"git add {file_path}")
    
    # Commit
    commit_msg = f"chore: release {tag_name}"
    run_command(f'git commit -m "{commit_msg}"')
    
    # Tag
    run_command(f"git tag {tag_name}")
    
    print(f"Successfully tagged {tag_name}")
    print("To publish, run: git push && git push --tags")

def main():
    parser = argparse.ArgumentParser(description="Automate release versioning")
    parser.add_argument("version", help="New version number (e.g. 1.1.0)")
    parser.add_argument("--dry-run", action="store_true", help="Do not run git commands or write files")
    
    args = parser.parse_args()
    
    print(f"Preparing release {args.version}...")
    
    if args.dry_run:
        print("[DRY RUN] Would update README.md and version.py")
        print(f"[DRY RUN] Would commit and tag v{args.version}")
    else:
        updated_readme = update_readme(args.version)
        updated_version = update_version_py(args.version)
        extract_release_notes(args.version)
        git_commit_and_tag(args.version, [updated_readme, updated_version])

if __name__ == "__main__":
    main()
