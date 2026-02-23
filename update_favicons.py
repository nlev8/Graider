import os

blog_dir = 'landing/blog'
files = [
    'graider-vs-cograder.html',
    'graider-vs-gradescope.html',
    'graider-vs-essaygrader.html',
    'best-ai-grading-tools.html'
]

def update_html(filepath, prefix=""):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # We want to add these lines where the old favicon was:
    old_favicon = f'<link rel="icon" type="image/png" href="{prefix}favicon.png">'
    new_favicons = f"""<link rel="icon" href="{prefix}favicon.ico" sizes="32x32">
    <link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
    {old_favicon}"""

    if old_favicon in content and new_favicons not in content:
        content = content.replace(old_favicon, new_favicons)
    elif '<link rel="icon" type="image/png" href="../favicon.png">' in content:
        # handle blog files relative paths
        old_blog_favicon = '<link rel="icon" type="image/png" href="../favicon.png">'
        new_blog_favicons = f"""<link rel="icon" href="../favicon.ico" sizes="32x32">
    <link rel="icon" href="../favicon.svg" type="image/svg+xml">
    {old_blog_favicon}"""
        if new_blog_favicons not in content:
            content = content.replace(old_blog_favicon, new_blog_favicons)

    with open(filepath, 'w') as f:
        f.write(content)

for file in files:
    update_html(os.path.join(blog_dir, file), prefix="../")

update_html('landing/index.html', prefix="/")

print("Favicon tags updated successfully in HTML files.")
