import os
import shutil

# Target directory
target_dir = "datasets"
os.makedirs(target_dir, exist_ok=True)

# Files to move
files_to_move = [
    "CS_Dataset_Phase2.json",
    "CS_Dataset_Phase2.xlsx",
    "udemy_tech.csv",
    "courses_en.csv",
    "EdX.csv",
    "Online_Courses.csv"
]

print("Starting file migration to datasets/ folder...")
moved_count = 0
for filename in files_to_move:
    if os.path.exists(filename):
        target_path = os.path.join(target_dir, filename)
        shutil.move(filename, target_path)
        print(f"Relocated: '{filename}' -> '{target_path}'")
        moved_count += 1

print(f"Migration complete! Moved {moved_count} dataset files successfully.")
