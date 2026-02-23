# Prompt for Claude Code: Playwright Script Generation

Copy and paste this to Claude Code, filling in your app details:

---

Create a Playwright automation script for my app with the following:

## App Details
- **URL:** [your app URL]
- **Login required:** [yes/no]
- **Credentials:** [username/password or "already logged in"]
- **2FA:** [yes/no, if yes describe method]

## Task to Automate
[Describe what you want automated, e.g., "Create a new assignment with name, due date, points, and description"]

## Workflow Steps
1. [First step, e.g., "Click 'New Assignment' button"]
2. [Second step, e.g., "Fill 'Name' field"]
3. [Third step, e.g., "Select category from dropdown"]
4. [Continue with all steps...]
5. [Final step, e.g., "Click Save"]

## HTML Structure
[Paste the HTML of the form/section - see instructions below]

### How to Get HTML:
1. Open your app in Chrome/Edge
2. Right-click on the form → "Inspect"
3. In DevTools, right-click the form element → Copy → Copy outerHTML
4. Paste here

## Field Details
| Field Name | Type | Required | Notes |
|------------|------|----------|-------|
| Name | text input | yes | Assignment name |
| Category | dropdown | yes | Options: Homework, Quiz, Test |
| Points | number input | yes | Default: 100 |
| Due Date | date picker | yes | Format: MM/DD/YYYY |
| Description | textarea | no | Optional notes |

## Example Data
- Name: "Quiz 1 - Chapter 3"
- Category: "Quiz"
- Points: 50
- Due Date: "02/15/2026"
- Description: "Covers sections 3.1-3.3"

## Script Requirements
- Use Playwright (Node.js)
- Launch browser visible (headless: false)
- Take screenshots on errors
- Log each step to console
- Leave browser open for X seconds after completion for review
- CLI arguments: `--name`, `--category`, `--points`, `--date`, `--description`

## Additional Notes
[Any special considerations: dynamic content, AJAX calls, confirmation dialogs, etc.]

---

## Example Complete Prompt

Here's a filled-in example:

```
Create a Playwright automation script for my app with the following:

## App Details
- URL: https://myschool.gradebook.com
- Login required: yes
- Credentials: teacher@school.edu / MyPassword123
- 2FA: no

## Task to Automate
Create a new assignment in the gradebook with name, category, points, due date, and description

## Workflow Steps
1. Navigate to https://myschool.gradebook.com
2. Click "Login" button
3. Fill email field with teacher@school.edu
4. Fill password field
5. Click "Sign In"
6. Click "Assignments" tab
7. Click "New Assignment" button
8. Fill assignment form
9. Click "Save"

## HTML Structure
<form id="assignment-form">
  <input id="assignment-name" name="name" type="text" placeholder="Assignment Name" />
  <select id="category" name="category">
    <option value="homework">Homework</option>
    <option value="quiz">Quiz</option>
    <option value="test">Test</option>
  </select>
  <input id="points" name="points" type="number" value="100" />
  <input id="due-date" name="dueDate" type="date" />
  <textarea id="description" name="description"></textarea>
  <button type="submit">Save Assignment</button>
</form>

## Field Details
| Field Name | Type | Required | Notes |
|------------|------|----------|-------|
| Name | text input | yes | #assignment-name |
| Category | dropdown | yes | #category |
| Points | number input | yes | #points |
| Due Date | date picker | yes | #due-date |
| Description | textarea | no | #description |

## Example Data
- Name: "Quiz 1 - Chapter 3"
- Category: "quiz"
- Points: 50
- Due Date: "2026-02-15"
- Description: "Covers sections 3.1-3.3"

## Script Requirements
- Use Playwright (Node.js)
- Launch browser visible (headless: false)
- Take screenshots on errors
- Log each step to console
- Leave browser open for 60 seconds after completion
- CLI arguments: --name, --category, --points, --date, --description

## Additional Notes
- Form submission triggers AJAX save (wait for success message)
- Success message appears as: <div class="alert-success">Assignment created</div>
```

---

## Quick HTML Extraction Script

Or run this in your browser console to get the HTML automatically:

```javascript
// Click on the form first, then run:
copy(document.querySelector('form').outerHTML);
// HTML is now in your clipboard - paste into prompt
```
