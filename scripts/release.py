
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

def git_commit_and_tag(version, file_path):
    tag_name = f"v{version}"
    print(f"Creating git release for {tag_name}...")
    
    # Add changed files
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
        print("[DRY RUN] Would update README.md")
        print(f"[DRY RUN] Would commit and tag v{args.version}")
    else:
        updated_file = update_readme(args.version)
        git_commit_and_tag(args.version, updated_file)

if __name__ == "__main__":
    main()
