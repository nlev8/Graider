import os
import re

blog_dir = 'landing/blog'
files = [
    'graider-vs-cograder.html',
    'graider-vs-gradescope.html',
    'graider-vs-essaygrader.html',
    'best-ai-grading-tools.html'
]
index_file = 'landing/index.html'

internal_links_html = """
            <!-- Related Posts -->
            <div class="related-posts" style="margin: 4rem 0; padding: 2rem; background: #f8fafc; border-radius: 12px; border: 1px solid #e2e8f0;">
                <h3 style="margin-top: 0; font-size: 1.25rem; color: #0f172a;">More Reviews & Comparisons</h3>
                <ul style="margin-bottom: 0; padding-left: 1.5rem; color: #3b82f6;">
                    <li><a href="/blog/best-ai-grading-tools" style="color: #2563eb; text-decoration: none; font-weight: 500;">Best AI Grading Tools for Teachers in 2026: Complete Guide</a></li>
                    <li><a href="/blog/graider-vs-cograder" style="color: #2563eb; text-decoration: none; font-weight: 500;">Graider vs CoGrader: Detailed Comparison</a></li>
                    <li><a href="/blog/graider-vs-gradescope" style="color: #2563eb; text-decoration: none; font-weight: 500;">Graider vs Gradescope: Which is Better for K-12?</a></li>
                    <li><a href="/blog/graider-vs-essaygrader" style="color: #2563eb; text-decoration: none; font-weight: 500;">Graider vs EssayGrader: Head-to-Head Analysis</a></li>
                </ul>
            </div>
"""

def update_html(filepath, is_blog=True):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # 1. Add meta robots if missing
    if '<meta name="robots"' not in content:
        content = re.sub(r'(<meta name="twitter:card".*?>)', r'<meta name="robots" content="index, follow">\n    \1', content)
        
    # 2. Add article:published_time if missing (only for blogs)
    if is_blog and '<meta property="article:published_time"' not in content:
        content = re.sub(r'(<meta name="twitter:card".*?>)', r'<meta property="article:published_time" content="2026-02-21">\n    \1', content)

    # 3. Remove Google Fonts
    content = re.sub(r'<link rel="preconnect" href="https://fonts\.googleapis\.com".*?>\n\s*', '', content)
    content = re.sub(r'<link rel="preconnect" href="https://fonts\.gstatic\.com".*?>\n\s*', '', content)
    content = re.sub(r'<link href="https://fonts\.googleapis\.com/css2.*?>\n\s*', '', content)
    
    # 4. Inject internal links (only for blogs)
    if is_blog and '<!-- Related Posts -->' not in content:
        content = content.replace('<!-- CTA -->', internal_links_html + '\n            <!-- CTA -->')

    with open(filepath, 'w') as f:
        f.write(content)

for file in files:
    update_html(os.path.join(blog_dir, file), is_blog=True)

update_html(index_file, is_blog=False)

print("HTML files updated successfully.")
