"""Generate the professional slide template for Graider.

Run once: python backend/scripts/create_slide_template.py
Creates: backend/templates/slide_template.pptx

This template has 6 slide layouts:
  0: Title Slide (big title, subtitle, full-width image area)
  1: Content Slide (title + bullet points, image on right)
  2: Image Focus (large image with caption below)
  3: Two Column (title + two columns of content)
  4: Key Concept (centered large text with accent background)
  5: Section Divider (section title with decorative bar)
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# Create presentation with 16:9 aspect ratio
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# Access the slide master
slide_master = prs.slide_masters[0]

# We'll create layouts by adding slides and using them as reference.
# python-pptx has limited layout creation — instead we create a minimal
# template with a blank layout and handle positioning in code.

# For now, create a single blank layout template.
# The slide_generator.py will handle all positioning programmatically
# using the layout type specified in the JSON.

# Add a blank slide as the only layout
blank_layout = prs.slide_layouts[6]  # Index 6 is typically "Blank"

output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "slide_template.pptx")
prs.save(output_path)
print("Template saved to: " + output_path)
