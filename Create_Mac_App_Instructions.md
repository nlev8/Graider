# How to Create the Assignment Grader Mac App

## Quick Setup (5 minutes)

### Step 1: Put Files in Place

Make sure these files are in `/Users/alexc/Downloads/Assignment Grader/`:
- `assignment_grader.py` (the main grading script)
- `grader_gui.py` (the GUI app)
- `all_students_updated.xlsx` (student roster)
- `.env` (with your OpenAI API key)

### Step 2: Create the App with Automator

1. Open **Automator** (search for it in Spotlight with Cmd+Space)

2. Click **File → New** (or press Cmd+N)

3. Select **Application** and click **Choose**

4. In the search bar on the left, type "Run Shell Script"

5. Drag **Run Shell Script** to the right panel

6. In the shell script box, paste this:
```bash
cd "/Users/alexc/Downloads/Assignment Grader"
/usr/bin/python3 grader_gui.py
```

7. Click **File → Save** (Cmd+S)

8. Name it: `Assignment Grader`

9. Save it to: Desktop (or Applications folder)

10. Done! You now have an app you can double-click.

---

## Optional: Add a Custom Icon

1. Find an icon image you like (PNG or ICNS format)
   - You can use an emoji image or school-related icon
   - Or download one from flaticon.com or similar

2. Open the image in Preview

3. Press Cmd+A (select all) then Cmd+C (copy)

4. Right-click your **Assignment Grader.app** and select **Get Info**

5. Click the small icon in the top-left of the info window

6. Press Cmd+V (paste)

7. Close the info window

---

## Alternative: Simple Terminal Shortcut

If you prefer not to use Automator, you can also create an alias:

1. Open Terminal

2. Run this command:
```bash
echo 'alias grade="cd /Users/alexc/Downloads/Assignment\ Grader && python3 grader_gui.py"' >> ~/.zshrc
```

3. Restart Terminal

4. Now just type `grade` in Terminal to launch the app

---

## Troubleshooting

### "Python not found" error
Make sure Python 3 is installed:
```bash
python3 --version
```
If not installed, download from python.org or run:
```bash
xcode-select --install
```

### "Module not found" errors
Install required packages:
```bash
pip3 install openai python-docx openpyxl python-dotenv
```

### App won't open (security warning)
1. Go to **System Preferences → Security & Privacy**
2. Click **Open Anyway** next to the blocked app message
3. Or right-click the app and select **Open** the first time

### GUI doesn't appear
Make sure tkinter is installed (it comes with Python on Mac, but just in case):
```bash
brew install python-tk
```

---

## What the App Does

When you open the Assignment Grader app:

1. **Select folders** - Choose where assignments are and where to save results
2. **Click Start Grading** - The AI grades all assignments automatically
3. **View progress** - Watch the log as each file is processed
4. **Get results** - CSV files ready for Focus import + feedback emails

---

## File Locations (Defaults)

| What | Where |
|------|-------|
| Student Assignments | `/Users/alexc/Downloads/Assignments` |
| Results (CSVs, emails) | `/Users/alexc/Downloads/Assignment Grader/Results` |
| Student Roster | `/Users/alexc/Downloads/Assignment Grader/all_students_updated.xlsx` |
| API Key | `/Users/alexc/Downloads/Assignment Grader/.env` |
