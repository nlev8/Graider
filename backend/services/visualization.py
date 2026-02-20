"""
Visualization Service for Graider
=================================
Generates graphs, charts, and diagrams for math/science assignments.

Supports:
- Number lines (for rational numbers)
- Coordinate planes (4 quadrants)
- Box plots (statistics)
- Bar/line/scatter charts (data analysis)
- Geometric shapes (triangles, rectangles)
"""

import io
import base64
from pathlib import Path

# Lazy import matplotlib to avoid startup overhead
_plt = None
_np = None


def _get_plt():
    """Lazy load matplotlib."""
    global _plt
    if _plt is None:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        _plt = plt
    return _plt


def _get_np():
    """Lazy load numpy."""
    global _np
    if _np is None:
        import numpy as np
        _np = np
    return _np


def figure_to_base64(fig) -> str:
    """Convert matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    return f"data:image/png;base64,{img_str}"


def save_figure(fig, filepath: str):
    """Save matplotlib figure to file."""
    fig.savefig(filepath, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')


# =============================================================================
# LATEX / MATH NOTATION
# =============================================================================

def render_latex(latex: str, font_size: int = 20) -> str:
    """Render a LaTeX math expression to a base64 PNG using matplotlib mathtext.

    Supports fractions, exponents, roots, integrals, summations, Greek letters,
    and most standard LaTeX math notation — no external LaTeX install needed.

    Args:
        latex: LaTeX math string (e.g., r'\\frac{1}{2}').
        font_size: Font size for the rendered expression.

    Returns:
        Base64 encoded PNG image string (data:image/png;base64,...).
    """
    plt = _get_plt()

    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0.5, 0.5, f"${latex}$", fontsize=font_size,
             ha='center', va='center',
             transform=fig.transFigure)
    fig.patch.set_alpha(0)

    # Render to buffer to calculate bounding box, then re-render tight
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                pad_inches=0.1, facecolor='white', edgecolor='none')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close(fig)

    return f"data:image/png;base64,{img_str}"


# =============================================================================
# NUMBER LINES
# =============================================================================

def create_number_line(
    min_val: float = -10,
    max_val: float = 10,
    points: list = None,
    labels: list = None,
    title: str = None,
    show_integers: bool = True,
    blank: bool = False
) -> str:
    """
    Create a number line with optional plotted points.

    Args:
        min_val: Minimum value on the line
        max_val: Maximum value on the line
        points: List of values to plot as points
        labels: Labels for the points (e.g., ['A', 'B', 'C'])
        title: Title above the number line
        show_integers: Show integer tick marks
        blank: If True, create blank number line for students to fill in

    Returns:
        Base64 encoded PNG image
    """
    plt = _get_plt()
    np = _get_np()

    fig, ax = plt.subplots(figsize=(10, 2))

    # Draw the main line
    ax.axhline(y=0, color='black', linewidth=2)
    ax.set_xlim(min_val - 0.5, max_val + 0.5)
    ax.set_ylim(-0.5, 0.8)

    # Draw tick marks
    if show_integers:
        for i in range(int(min_val), int(max_val) + 1):
            ax.plot([i, i], [-0.1, 0.1], 'k-', linewidth=1.5)
            if not blank:
                ax.text(i, -0.25, str(i), ha='center', va='top', fontsize=10)

    # Draw arrows at ends
    ax.annotate('', xy=(max_val + 0.3, 0), xytext=(max_val, 0),
                arrowprops=dict(arrowstyle='->', color='black', lw=2))
    ax.annotate('', xy=(min_val - 0.3, 0), xytext=(min_val, 0),
                arrowprops=dict(arrowstyle='->', color='black', lw=2))

    # Plot points if provided
    if points and not blank:
        colors = plt.cm.tab10(np.linspace(0, 1, len(points)))
        for i, (pt, color) in enumerate(zip(points, colors)):
            ax.plot(pt, 0, 'o', markersize=12, color=color, zorder=5)
            if labels and i < len(labels):
                ax.text(pt, 0.3, labels[i], ha='center', va='bottom',
                       fontsize=12, fontweight='bold', color=color)

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')

    ax.axis('off')
    plt.tight_layout()

    result = figure_to_base64(fig)
    plt.close(fig)
    return result


# =============================================================================
# COORDINATE PLANE
# =============================================================================

def create_coordinate_plane(
    x_range: tuple = (-10, 10),
    y_range: tuple = (-10, 10),
    points: list = None,
    labels: list = None,
    title: str = None,
    grid: bool = True,
    blank: bool = False
) -> str:
    """
    Create a coordinate plane with optional plotted points.

    Args:
        x_range: (min, max) for x-axis
        y_range: (min, max) for y-axis
        points: List of (x, y) tuples to plot
        labels: Labels for the points
        title: Title for the graph
        grid: Show grid lines
        blank: If True, create blank plane for students

    Returns:
        Base64 encoded PNG image
    """
    plt = _get_plt()
    np = _get_np()

    fig, ax = plt.subplots(figsize=(8, 8))

    # Set up the axes
    ax.set_xlim(x_range[0] - 0.5, x_range[1] + 0.5)
    ax.set_ylim(y_range[0] - 0.5, y_range[1] + 0.5)

    # Draw axes through origin
    ax.axhline(y=0, color='black', linewidth=1.5)
    ax.axvline(x=0, color='black', linewidth=1.5)

    # Grid
    if grid:
        ax.grid(True, linestyle='--', alpha=0.5)

    # Tick marks
    ax.set_xticks(range(x_range[0], x_range[1] + 1))
    ax.set_yticks(range(y_range[0], y_range[1] + 1))

    # Labels for quadrants
    offset = (x_range[1] - x_range[0]) * 0.4
    ax.text(offset, offset, 'I', fontsize=16, color='gray', alpha=0.5)
    ax.text(-offset, offset, 'II', fontsize=16, color='gray', alpha=0.5)
    ax.text(-offset, -offset, 'III', fontsize=16, color='gray', alpha=0.5)
    ax.text(offset, -offset, 'IV', fontsize=16, color='gray', alpha=0.5)

    # Axis labels
    ax.set_xlabel('x', fontsize=12)
    ax.set_ylabel('y', fontsize=12)

    # Plot points if provided
    if points and not blank:
        colors = plt.cm.tab10(np.linspace(0, 1, len(points)))
        for i, (pt, color) in enumerate(zip(points, colors)):
            ax.plot(pt[0], pt[1], 'o', markersize=10, color=color, zorder=5)
            label = labels[i] if labels and i < len(labels) else f"({pt[0]}, {pt[1]})"
            ax.annotate(label, xy=pt, xytext=(5, 5), textcoords='offset points',
                       fontsize=10, fontweight='bold', color=color)

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')

    ax.set_aspect('equal')
    plt.tight_layout()

    result = figure_to_base64(fig)
    plt.close(fig)
    return result


# =============================================================================
# BOX PLOTS
# =============================================================================

def create_box_plot(
    data: list,
    labels: list = None,
    title: str = None,
    show_values: bool = True,
    blank: bool = False
) -> str:
    """
    Create a box plot for statistical analysis.

    Args:
        data: List of data sets (each is a list of values)
        labels: Labels for each data set
        title: Title for the graph
        show_values: Show min, Q1, median, Q3, max values
        blank: If True, create blank template

    Returns:
        Base64 encoded PNG image
    """
    plt = _get_plt()
    np = _get_np()

    fig, ax = plt.subplots(figsize=(10, 4))

    if not blank and data:
        bp = ax.boxplot(data, patch_artist=True, labels=labels or [f'Set {i+1}' for i in range(len(data))])

        # Color the boxes
        colors = plt.cm.Pastel1(np.linspace(0, 1, len(data)))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)

        # Show values if requested
        if show_values:
            for i, d in enumerate(data):
                stats = {
                    'min': min(d),
                    'Q1': np.percentile(d, 25),
                    'median': np.median(d),
                    'Q3': np.percentile(d, 75),
                    'max': max(d)
                }
                # Add annotation
                y_offset = max(d) * 0.1
                ax.text(i + 1, max(d) + y_offset,
                       f"Min:{stats['min']:.1f} Q1:{stats['Q1']:.1f}\nMed:{stats['median']:.1f} Q3:{stats['Q3']:.1f} Max:{stats['max']:.1f}",
                       ha='center', fontsize=8, va='bottom')
    else:
        # Blank template
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 10)
        ax.axhline(y=5, color='black', linewidth=1)
        ax.text(50, 5, 'Draw your box plot here', ha='center', va='center',
               fontsize=12, color='gray')

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')

    ax.set_ylabel('Value')
    plt.tight_layout()

    result = figure_to_base64(fig)
    plt.close(fig)
    return result


# =============================================================================
# BAR/LINE/SCATTER CHARTS
# =============================================================================

def create_bar_chart(
    categories: list,
    values: list,
    title: str = None,
    x_label: str = None,
    y_label: str = None,
    color: str = 'steelblue',
    blank: bool = False
) -> str:
    """Create a bar chart."""
    plt = _get_plt()
    np = _get_np()

    fig, ax = plt.subplots(figsize=(8, 5))

    if not blank and categories and values:
        bars = ax.bar(categories, values, color=color, edgecolor='black')

        # Add value labels on top of bars
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                   str(val), ha='center', va='bottom', fontsize=10)
    else:
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.text(5, 5, 'Draw your bar chart here', ha='center', va='center',
               fontsize=12, color='gray')

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)

    plt.tight_layout()
    result = figure_to_base64(fig)
    plt.close(fig)
    return result


def create_line_graph(
    x_data: list,
    y_data: list,
    title: str = None,
    x_label: str = None,
    y_label: str = None,
    show_points: bool = True,
    blank: bool = False
) -> str:
    """Create a line graph."""
    plt = _get_plt()

    fig, ax = plt.subplots(figsize=(8, 5))

    if not blank and x_data and y_data:
        ax.plot(x_data, y_data, 'b-', linewidth=2)
        if show_points:
            ax.plot(x_data, y_data, 'ro', markersize=8)
        ax.grid(True, linestyle='--', alpha=0.5)
    else:
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.text(5, 5, 'Plot your data here', ha='center', va='center',
               fontsize=12, color='gray')

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)

    plt.tight_layout()
    result = figure_to_base64(fig)
    plt.close(fig)
    return result


def create_scatter_plot(
    x_data: list,
    y_data: list,
    title: str = None,
    x_label: str = None,
    y_label: str = None,
    show_trend: bool = False,
    blank: bool = False
) -> str:
    """Create a scatter plot."""
    plt = _get_plt()
    np = _get_np()

    fig, ax = plt.subplots(figsize=(8, 5))

    if not blank and x_data and y_data:
        ax.scatter(x_data, y_data, c='steelblue', s=80, alpha=0.7, edgecolors='black')

        if show_trend:
            z = np.polyfit(x_data, y_data, 1)
            p = np.poly1d(z)
            ax.plot(x_data, p(x_data), 'r--', linewidth=2, label='Trend line')
            ax.legend()

        ax.grid(True, linestyle='--', alpha=0.5)
    else:
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.text(5, 5, 'Plot your data points here', ha='center', va='center',
               fontsize=12, color='gray')

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')
    if x_label:
        ax.set_xlabel(x_label)
    if y_label:
        ax.set_ylabel(y_label)

    plt.tight_layout()
    result = figure_to_base64(fig)
    plt.close(fig)
    return result


# =============================================================================
# GEOMETRIC SHAPES
# =============================================================================

def create_triangle(
    base: float = 6,
    height: float = 4,
    show_labels: bool = True,
    show_dimensions: bool = True,
    title: str = None,
    blank: bool = False
) -> str:
    """Create a triangle diagram."""
    plt = _get_plt()

    fig, ax = plt.subplots(figsize=(6, 5))

    if not blank:
        # Triangle vertices
        vertices = [(0, 0), (base, 0), (base/2, height)]
        triangle = plt.Polygon(vertices, fill=True, facecolor='lightblue',
                              edgecolor='black', linewidth=2)
        ax.add_patch(triangle)

        # Height line (dashed)
        ax.plot([base/2, base/2], [0, height], 'r--', linewidth=1.5)

        if show_dimensions:
            # Base label
            ax.text(base/2, -0.3, f'b = {base}', ha='center', fontsize=11)
            # Height label
            ax.text(base/2 + 0.3, height/2, f'h = {height}', ha='left', fontsize=11)

        if show_labels:
            ax.text(0, 0, 'A', ha='right', va='top', fontsize=12, fontweight='bold')
            ax.text(base, 0, 'B', ha='left', va='top', fontsize=12, fontweight='bold')
            ax.text(base/2, height, 'C', ha='center', va='bottom', fontsize=12, fontweight='bold')
    else:
        ax.text(0.5, 0.5, 'Draw triangle here', ha='center', va='center',
               transform=ax.transAxes, fontsize=12, color='gray')

    ax.set_xlim(-1, base + 1)
    ax.set_ylim(-1, height + 1)
    ax.set_aspect('equal')
    ax.axis('off')

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')

    plt.tight_layout()
    result = figure_to_base64(fig)
    plt.close(fig)
    return result


def create_rectangle(
    width: float = 6,
    height: float = 4,
    show_labels: bool = True,
    show_dimensions: bool = True,
    title: str = None,
    blank: bool = False
) -> str:
    """Create a rectangle diagram."""
    plt = _get_plt()

    fig, ax = plt.subplots(figsize=(6, 5))

    if not blank:
        rect = plt.Rectangle((0, 0), width, height, fill=True,
                             facecolor='lightgreen', edgecolor='black', linewidth=2)
        ax.add_patch(rect)

        if show_dimensions:
            ax.text(width/2, -0.3, f'w = {width}', ha='center', fontsize=11)
            ax.text(width + 0.3, height/2, f'h = {height}', ha='left', fontsize=11)

        if show_labels:
            ax.text(0, 0, 'A', ha='right', va='top', fontsize=12, fontweight='bold')
            ax.text(width, 0, 'B', ha='left', va='top', fontsize=12, fontweight='bold')
            ax.text(width, height, 'C', ha='left', va='bottom', fontsize=12, fontweight='bold')
            ax.text(0, height, 'D', ha='right', va='bottom', fontsize=12, fontweight='bold')
    else:
        ax.text(0.5, 0.5, 'Draw rectangle here', ha='center', va='center',
               transform=ax.transAxes, fontsize=12, color='gray')

    ax.set_xlim(-1, width + 1)
    ax.set_ylim(-1, height + 1)
    ax.set_aspect('equal')
    ax.axis('off')

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')

    plt.tight_layout()
    result = figure_to_base64(fig)
    plt.close(fig)
    return result


# =============================================================================
# FUNCTION GRAPHS
# =============================================================================

def create_function_graph(
    expressions: list,
    x_range: tuple = (-10, 10),
    y_range: tuple = None,
    title: str = None,
    show_grid: bool = True,
    labels: list = None,
    blank: bool = False
) -> str:
    """Plot mathematical functions on a coordinate plane.

    Args:
        expressions: List of expression strings, e.g. ["2*x + 1", "x**2"]
        x_range: (min, max) for x-axis
        y_range: (min, max) for y-axis, auto-calculated if None
        title: Graph title
        show_grid: Show grid lines
        labels: Legend labels for each expression
        blank: If True, draw empty axes for students to fill in

    Returns:
        Base64 encoded PNG image
    """
    plt = _get_plt()
    np = _get_np()

    fig, ax = plt.subplots(figsize=(8, 6))

    if not blank and expressions:
        from sympy import sympify, lambdify, Symbol
        x_sym = Symbol('x')
        x_vals = np.linspace(x_range[0], x_range[1], 400)

        colors = ['#2563eb', '#dc2626', '#16a34a', '#9333ea', '#ea580c']
        all_y = []

        for idx, expr_str in enumerate(expressions):
            # Clean expression: handle y= prefix, caret notation
            clean = expr_str.strip()
            if clean.lower().startswith('y'):
                clean = clean.split('=', 1)[-1].strip()
            clean = clean.replace('^', '**')

            try:
                sym_expr = sympify(clean)
                f = lambdify(x_sym, sym_expr, modules=['numpy'])
                y_vals = f(x_vals)

                # Handle arrays from constant expressions
                if not hasattr(y_vals, '__len__'):
                    y_vals = np.full_like(x_vals, float(y_vals))

                label = labels[idx] if labels and idx < len(labels) else f"y = {expr_str}"
                color = colors[idx % len(colors)]
                ax.plot(x_vals, y_vals, color=color, linewidth=2, label=label)
                all_y.extend(y_vals[np.isfinite(y_vals)])
            except Exception:
                continue

        if labels or len(expressions) > 1:
            ax.legend(fontsize=10)

        # Auto y-range if not specified
        if y_range is None and all_y:
            y_min = max(np.percentile(all_y, 2), -50)
            y_max = min(np.percentile(all_y, 98), 50)
            margin = (y_max - y_min) * 0.1 or 1
            ax.set_ylim(y_min - margin, y_max + margin)
        elif y_range:
            ax.set_ylim(y_range)
    else:
        if y_range:
            ax.set_ylim(y_range)
        else:
            ax.set_ylim(-10, 10)

    ax.set_xlim(x_range)
    ax.axhline(y=0, color='black', linewidth=0.8)
    ax.axvline(x=0, color='black', linewidth=0.8)

    if show_grid:
        ax.grid(True, linestyle='--', alpha=0.4)

    ax.set_xlabel('x', fontsize=12)
    ax.set_ylabel('y', fontsize=12)

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')

    plt.tight_layout()
    result = figure_to_base64(fig)
    plt.close(fig)
    return result


# =============================================================================
# CIRCLES
# =============================================================================

def create_circle(
    radius: float = 5,
    center: tuple = (0, 0),
    show_radius: bool = True,
    show_diameter: bool = False,
    show_area: bool = False,
    title: str = None,
    blank: bool = False
) -> str:
    """Create a circle diagram with optional radius/diameter/area labels.

    Args:
        radius: Circle radius
        center: (x, y) center coordinates
        show_radius: Draw and label radius line
        show_diameter: Draw and label diameter line
        show_area: Show area formula/value
        title: Diagram title
        blank: If True, draw unlabeled circle

    Returns:
        Base64 encoded PNG image
    """
    plt = _get_plt()
    np = _get_np()

    fig, ax = plt.subplots(figsize=(6, 6))

    circle_patch = plt.Circle(center, radius, fill=True,
                              facecolor='#dbeafe', edgecolor='#2563eb', linewidth=2)
    ax.add_patch(circle_patch)

    # Center dot
    ax.plot(center[0], center[1], 'ko', markersize=4)

    if not blank:
        if show_radius:
            ax.plot([center[0], center[0] + radius], [center[1], center[1]],
                    'r-', linewidth=1.5)
            ax.text(center[0] + radius / 2, center[1] + radius * 0.08,
                    f'r = {radius}', ha='center', fontsize=11, color='red')

        if show_diameter:
            ax.plot([center[0] - radius, center[0] + radius],
                    [center[1], center[1]], 'g--', linewidth=1.5)
            ax.text(center[0], center[1] - radius * 0.12,
                    f'd = {radius * 2}', ha='center', fontsize=11, color='green')

        if show_area:
            import math
            area = math.pi * radius ** 2
            ax.text(center[0], center[1] - radius * 0.3,
                    f'A = {area:.2f}', ha='center', fontsize=10, color='#6b7280')

    margin = radius * 0.4
    ax.set_xlim(center[0] - radius - margin, center[0] + radius + margin)
    ax.set_ylim(center[1] - radius - margin, center[1] + radius + margin)
    ax.set_aspect('equal')
    ax.axis('off')

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')

    plt.tight_layout()
    result = figure_to_base64(fig)
    plt.close(fig)
    return result


# =============================================================================
# REGULAR POLYGONS
# =============================================================================

def create_polygon(
    sides: int = 5,
    side_length: float = 4,
    show_labels: bool = True,
    show_dimensions: bool = True,
    title: str = None,
    blank: bool = False
) -> str:
    """Create a regular polygon diagram.

    Args:
        sides: Number of sides (3=triangle, 4=square, 5=pentagon, etc.)
        side_length: Length of each side
        show_labels: Label vertices A, B, C...
        show_dimensions: Show side length labels
        title: Diagram title
        blank: If True, draw unlabeled polygon

    Returns:
        Base64 encoded PNG image
    """
    plt = _get_plt()
    np = _get_np()

    fig, ax = plt.subplots(figsize=(6, 6))

    # Compute vertices of regular polygon centered at origin
    # Rotate so bottom edge is horizontal
    offset_angle = -np.pi / 2 + np.pi / sides
    angles = [offset_angle + 2 * np.pi * k / sides for k in range(sides)]
    circumradius = side_length / (2 * np.sin(np.pi / sides))
    vertices = [(circumradius * np.cos(a), circumradius * np.sin(a)) for a in angles]

    polygon = plt.Polygon(vertices, fill=True, facecolor='#fef3c7',
                          edgecolor='#d97706', linewidth=2)
    ax.add_patch(polygon)

    if not blank:
        vertex_labels = [chr(65 + i) for i in range(sides)]  # A, B, C, ...
        for i, (vx, vy) in enumerate(vertices):
            if show_labels:
                # Place label outside the polygon
                dx = vx - 0
                dy = vy - 0
                dist = np.sqrt(dx**2 + dy**2) or 1
                lx = vx + dx / dist * circumradius * 0.15
                ly = vy + dy / dist * circumradius * 0.15
                ax.text(lx, ly, vertex_labels[i], ha='center', va='center',
                        fontsize=12, fontweight='bold')

            if show_dimensions:
                # Label the side between this vertex and the next
                nx, ny = vertices[(i + 1) % sides]
                mx, my = (vx + nx) / 2, (vy + ny) / 2
                # Offset label outward
                sx, sy = nx - vx, ny - vy
                norm = np.sqrt(sx**2 + sy**2) or 1
                ox, oy = -sy / norm * circumradius * 0.1, sx / norm * circumradius * 0.1
                ax.text(mx + ox, my + oy, f'{side_length}', ha='center',
                        va='center', fontsize=10, color='#92400e')

    margin = circumradius * 0.3
    ax.set_xlim(-circumradius - margin, circumradius + margin)
    ax.set_ylim(-circumradius - margin, circumradius + margin)
    ax.set_aspect('equal')
    ax.axis('off')

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')

    plt.tight_layout()
    result = figure_to_base64(fig)
    plt.close(fig)
    return result


# =============================================================================
# HISTOGRAMS
# =============================================================================

def create_histogram(
    data: list,
    bins: int = 10,
    title: str = None,
    x_label: str = None,
    y_label: str = "Frequency",
    show_values: bool = True,
    blank: bool = False
) -> str:
    """Create a histogram for frequency distribution.

    Args:
        data: List of numeric values
        bins: Number of bins
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        show_values: Show frequency count on top of each bar
        blank: If True, draw empty axes

    Returns:
        Base64 encoded PNG image
    """
    plt = _get_plt()

    fig, ax = plt.subplots(figsize=(8, 5))

    if not blank and data:
        n, bin_edges, patches = ax.hist(data, bins=bins, color='steelblue',
                                         edgecolor='black', alpha=0.8)
        if show_values:
            for count, patch in zip(n, patches):
                if count > 0:
                    ax.text(patch.get_x() + patch.get_width() / 2, count + 0.3,
                            str(int(count)), ha='center', va='bottom', fontsize=9)
    else:
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.text(5, 5, 'Draw your histogram here', ha='center', va='center',
                fontsize=12, color='gray')

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')
    if x_label:
        ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)

    plt.tight_layout()
    result = figure_to_base64(fig)
    plt.close(fig)
    return result


# =============================================================================
# PIE CHARTS
# =============================================================================

def create_pie_chart(
    categories: list,
    values: list,
    title: str = None,
    show_percentages: bool = True,
    explode: list = None,
    blank: bool = False
) -> str:
    """Create a pie chart for part-of-whole visualization.

    Args:
        categories: List of category labels
        values: List of numeric values
        title: Chart title
        show_percentages: Show percentage labels on slices
        explode: List of float offsets for exploded slices (e.g. [0, 0.1, 0])
        blank: If True, draw empty circle placeholder

    Returns:
        Base64 encoded PNG image
    """
    plt = _get_plt()

    fig, ax = plt.subplots(figsize=(7, 5))

    if not blank and categories and values:
        autopct = '%1.1f%%' if show_percentages else None
        colors = plt.cm.Set3([i / max(len(values), 1) for i in range(len(values))])
        ax.pie(values, labels=categories, autopct=autopct, colors=colors,
               explode=explode, startangle=90, textprops={'fontsize': 10})
        ax.axis('equal')
    else:
        circle = plt.Circle((0.5, 0.5), 0.4, fill=False, edgecolor='gray',
                             linewidth=2, linestyle='--')
        ax.add_patch(circle)
        ax.text(0.5, 0.5, 'Draw your pie chart here', ha='center', va='center',
                fontsize=12, color='gray')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect('equal')
        ax.axis('off')

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')

    plt.tight_layout()
    result = figure_to_base64(fig)
    plt.close(fig)
    return result


# =============================================================================
# SAVE TO DOCX
# =============================================================================

def add_image_to_docx(doc, image_base64: str, width_inches: float = 5):
    """
    Add a base64 image to a Word document.

    Args:
        doc: python-docx Document object
        image_base64: Base64 encoded image (with or without data: prefix)
        width_inches: Width of the image in inches
    """
    from docx.shared import Inches

    # Remove data URL prefix if present
    if image_base64.startswith('data:'):
        image_base64 = image_base64.split(',')[1]

    # Decode and save to temp buffer
    image_data = base64.b64decode(image_base64)
    image_stream = io.BytesIO(image_data)

    # Add to document
    doc.add_picture(image_stream, width=Inches(width_inches))
    image_stream.close()


# =============================================================================
# TESTING
# =============================================================================

if __name__ == '__main__':
    # Test each visualization
    print("Testing visualizations...")

    # Number line
    nl = create_number_line(points=[-3, 0.5, 2.75], labels=['A', 'B', 'C'],
                           title='Plot the rational numbers')
    print(f"Number line: {len(nl)} chars")

    # Coordinate plane
    cp = create_coordinate_plane(points=[(3, 4), (-2, 5), (-4, -3), (2, -5)],
                                labels=['A', 'B', 'C', 'D'],
                                title='Plot the points')
    print(f"Coordinate plane: {len(cp)} chars")

    # Box plot
    data = [[23, 45, 67, 32, 44, 55, 66, 77, 34, 45],
            [34, 56, 78, 43, 55, 66, 77, 88, 45, 56]]
    bp = create_box_plot(data, labels=['Class A', 'Class B'],
                        title='Test Scores by Class')
    print(f"Box plot: {len(bp)} chars")

    # Bar chart
    bc = create_bar_chart(['Math', 'Science', 'English', 'History'],
                         [85, 92, 78, 88], title='Average Grades by Subject')
    print(f"Bar chart: {len(bc)} chars")

    # Triangle
    tri = create_triangle(base=8, height=6, title='Find the Area')
    print(f"Triangle: {len(tri)} chars")

    print("All visualizations generated successfully!")
