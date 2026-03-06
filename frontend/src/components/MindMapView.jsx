import React, { useState, useRef, useEffect, useMemo } from "react";

/**
 * MindMapView — Visual radial mind map renderer.
 * Renders { name, children[] } tree as a Google-style mind map
 * with a central root node, radiating branches, and curved connectors.
 */

var BRANCH_COLORS = [
  "#8b5cf6", // purple
  "#ec4899", // pink
  "#3b82f6", // blue
  "#22c55e", // green
  "#f59e0b", // amber
  "#ef4444", // red
  "#06b6d4", // cyan
  "#f97316", // orange
];

function measureText(text, fontSize) {
  // Approximate text width: ~0.6 chars per fontSize unit
  return Math.min(text.length * fontSize * 0.55, 200);
}

function layoutTree(root) {
  // Compute positions for all nodes in a radial layout
  var nodes = [];
  var edges = [];
  var nodeId = 0;

  // Root at center
  var rootNode = {
    id: nodeId++,
    text: root.name,
    x: 0,
    y: 0,
    depth: 0,
    branchIndex: -1,
    children: root.children || [],
  };
  nodes.push(rootNode);

  var branches = root.children || [];
  var branchCount = branches.length;
  if (branchCount === 0) return { nodes: nodes, edges: edges };

  // Distribute branches evenly around the root
  // Top half gets more space for readability
  var angleStep = (2 * Math.PI) / branchCount;
  var startAngle = -Math.PI / 2; // Start from top

  branches.forEach(function(branch, bi) {
    var angle = startAngle + bi * angleStep;
    var radius1 = 220; // Distance from root to first level

    var bx = Math.cos(angle) * radius1;
    var by = Math.sin(angle) * radius1;

    var branchNode = {
      id: nodeId++,
      text: branch.name,
      x: bx,
      y: by,
      depth: 1,
      branchIndex: bi,
      children: branch.children || [],
    };
    nodes.push(branchNode);
    edges.push({ from: rootNode, to: branchNode, branchIndex: bi });

    // Layout children of each branch
    var children = branch.children || [];
    if (children.length > 0) {
      // Fan children out from the branch node
      var childSpread = Math.min(children.length * 0.35, 1.2);
      var childAngleStart = angle - childSpread / 2;
      var childAngleStep = children.length > 1 ? childSpread / (children.length - 1) : 0;
      var radius2 = 180;

      children.forEach(function(child, ci) {
        var childAngle = children.length === 1 ? angle : childAngleStart + ci * childAngleStep;
        var cx = bx + Math.cos(childAngle) * radius2;
        var cy = by + Math.sin(childAngle) * radius2;

        var childNode = {
          id: nodeId++,
          text: child.name,
          x: cx,
          y: cy,
          depth: 2,
          branchIndex: bi,
          children: child.children || [],
        };
        nodes.push(childNode);
        edges.push({ from: branchNode, to: childNode, branchIndex: bi });

        // Third level — smaller, tighter
        var grandchildren = child.children || [];
        if (grandchildren.length > 0) {
          var gcSpread = Math.min(grandchildren.length * 0.3, 0.9);
          var gcAngleStart = childAngle - gcSpread / 2;
          var gcAngleStep = grandchildren.length > 1 ? gcSpread / (grandchildren.length - 1) : 0;
          var radius3 = 140;

          grandchildren.forEach(function(gc, gi) {
            var gcAngle = grandchildren.length === 1 ? childAngle : gcAngleStart + gi * gcAngleStep;
            var gx = cx + Math.cos(gcAngle) * radius3;
            var gy = cy + Math.sin(gcAngle) * radius3;

            var gcNode = {
              id: nodeId++,
              text: gc.name,
              x: gx,
              y: gy,
              depth: 3,
              branchIndex: bi,
            };
            nodes.push(gcNode);
            edges.push({ from: childNode, to: gcNode, branchIndex: bi });
          });
        }
      });
    }
  });

  return { nodes: nodes, edges: edges };
}

function CurvedEdge({ from, to, color }) {
  // Draw a curved bezier path between two nodes
  var dx = to.x - from.x;
  var dy = to.y - from.y;
  // Control point: offset perpendicular to the midpoint
  var mx = (from.x + to.x) / 2;
  var my = (from.y + to.y) / 2;
  // Slight curve
  var cx1 = from.x + dx * 0.3;
  var cy1 = from.y + dy * 0.1;
  var cx2 = from.x + dx * 0.7;
  var cy2 = to.y - dy * 0.1;

  var d = "M " + from.x + " " + from.y + " C " + cx1 + " " + cy1 + ", " + cx2 + " " + cy2 + ", " + to.x + " " + to.y;

  return (
    <path
      d={d}
      fill="none"
      stroke={color}
      strokeWidth={from.depth === 0 ? 3 : 2}
      strokeOpacity={0.4}
      strokeLinecap="round"
    />
  );
}

function NodeBox({ node, color, onHover, hovered }) {
  var isRoot = node.depth === 0;
  var fontSize = isRoot ? 15 : node.depth === 1 ? 13 : 11;
  var padding = isRoot ? 18 : node.depth === 1 ? 12 : 8;
  var maxWidth = isRoot ? 180 : node.depth === 1 ? 160 : 140;

  // Word wrap text
  var words = node.text.split(" ");
  var lines = [];
  var currentLine = "";
  words.forEach(function(word) {
    var testLine = currentLine ? currentLine + " " + word : word;
    if (measureText(testLine, fontSize) > maxWidth) {
      if (currentLine) lines.push(currentLine);
      currentLine = word;
    } else {
      currentLine = testLine;
    }
  });
  if (currentLine) lines.push(currentLine);

  var lineHeight = fontSize * 1.3;
  var textHeight = lines.length * lineHeight;
  var boxWidth = Math.max.apply(null, lines.map(function(l) { return measureText(l, fontSize); })) + padding * 2;
  var boxHeight = textHeight + padding * 1.4;

  return (
    <g
      transform={"translate(" + node.x + "," + node.y + ")"}
      onMouseEnter={function() { onHover(node.id); }}
      onMouseLeave={function() { onHover(null); }}
      style={{ cursor: "default" }}
    >
      {/* Shadow */}
      {isRoot && (
        <rect
          x={-boxWidth / 2 + 2}
          y={-boxHeight / 2 + 2}
          width={boxWidth}
          height={boxHeight}
          rx={isRoot ? 16 : 10}
          fill="rgba(0,0,0,0.1)"
        />
      )}
      {/* Background */}
      <rect
        x={-boxWidth / 2}
        y={-boxHeight / 2}
        width={boxWidth}
        height={boxHeight}
        rx={isRoot ? 16 : 10}
        fill={isRoot ? color : (hovered ? color + "30" : color + "18")}
        stroke={color}
        strokeWidth={isRoot ? 0 : hovered ? 2 : 1}
        strokeOpacity={isRoot ? 0 : 0.5}
      />
      {/* Text */}
      {lines.map(function(line, li) {
        return (
          <text
            key={li}
            x={0}
            y={-textHeight / 2 + (li + 0.75) * lineHeight}
            textAnchor="middle"
            fill={isRoot ? "white" : "var(--text-primary)"}
            fontSize={fontSize}
            fontWeight={isRoot ? 700 : node.depth === 1 ? 600 : 400}
            fontFamily="system-ui, -apple-system, sans-serif"
          >
            {line}
          </text>
        );
      })}
    </g>
  );
}

export default function MindMapView({ data }) {
  var tree = data.mind_map || data;
  var [hoveredId, setHoveredId] = useState(null);
  var [pan, setPan] = useState({ x: 0, y: 0 });
  var [zoom, setZoom] = useState(1);
  var [dragging, setDragging] = useState(false);
  var dragStart = useRef(null);
  var containerRef = useRef(null);

  if (!tree || !tree.name) {
    return (
      <div style={{ padding: "20px", color: "var(--text-secondary)", fontStyle: "italic" }}>
        No mind map data available.
      </div>
    );
  }

  var layout = useMemo(function() { return layoutTree(tree); }, [tree]);

  // Compute SVG viewbox from node positions
  var bounds = useMemo(function() {
    var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    layout.nodes.forEach(function(n) {
      minX = Math.min(minX, n.x - 120);
      maxX = Math.max(maxX, n.x + 120);
      minY = Math.min(minY, n.y - 40);
      maxY = Math.max(maxY, n.y + 40);
    });
    var pad = 60;
    return {
      x: minX - pad,
      y: minY - pad,
      width: maxX - minX + pad * 2,
      height: maxY - minY + pad * 2,
    };
  }, [layout]);

  // Pan handlers
  function handleMouseDown(e) {
    setDragging(true);
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  }
  function handleMouseMove(e) {
    if (!dragging || !dragStart.current) return;
    setPan({ x: e.clientX - dragStart.current.x, y: e.clientY - dragStart.current.y });
  }
  function handleMouseUp() {
    setDragging(false);
    dragStart.current = null;
  }
  function handleWheel(e) {
    e.preventDefault();
    var delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(function(z) { return Math.max(0.3, Math.min(3, z * delta)); });
  }

  return (
    <div style={{ position: "relative" }}>
      {/* Zoom controls */}
      <div style={{ position: "absolute", top: "10px", right: "10px", zIndex: 10, display: "flex", gap: "4px" }}>
        <button
          onClick={function() { setZoom(function(z) { return Math.min(3, z * 1.2); }); }}
          style={{ width: "30px", height: "30px", borderRadius: "8px", border: "1px solid var(--border)", background: "var(--bg-primary)", cursor: "pointer", fontSize: "1rem", display: "flex", alignItems: "center", justifyContent: "center" }}
        >+</button>
        <button
          onClick={function() { setZoom(function(z) { return Math.max(0.3, z * 0.8); }); }}
          style={{ width: "30px", height: "30px", borderRadius: "8px", border: "1px solid var(--border)", background: "var(--bg-primary)", cursor: "pointer", fontSize: "1rem", display: "flex", alignItems: "center", justifyContent: "center" }}
        >{String.fromCharCode(8722)}</button>
        <button
          onClick={function() { setZoom(1); setPan({ x: 0, y: 0 }); }}
          style={{ height: "30px", borderRadius: "8px", border: "1px solid var(--border)", background: "var(--bg-primary)", cursor: "pointer", fontSize: "0.75rem", padding: "0 8px", display: "flex", alignItems: "center" }}
        >Reset</button>
      </div>

      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        style={{
          width: "100%",
          height: "480px",
          overflow: "hidden",
          cursor: dragging ? "grabbing" : "grab",
          borderRadius: "8px",
        }}
      >
        <svg
          width="100%"
          height="100%"
          viewBox={bounds.x + " " + bounds.y + " " + bounds.width + " " + bounds.height}
          style={{
            transform: "scale(" + zoom + ") translate(" + (pan.x / zoom) + "px, " + (pan.y / zoom) + "px)",
            transformOrigin: "center center",
          }}
        >
          {/* Edges first (behind nodes) */}
          {layout.edges.map(function(edge, i) {
            var color = BRANCH_COLORS[edge.branchIndex % BRANCH_COLORS.length];
            return <CurvedEdge key={"e" + i} from={edge.from} to={edge.to} color={color} />;
          })}

          {/* Nodes */}
          {layout.nodes.map(function(node) {
            var color = node.depth === 0
              ? "#8b5cf6"
              : BRANCH_COLORS[node.branchIndex % BRANCH_COLORS.length];
            return (
              <NodeBox
                key={node.id}
                node={node}
                color={color}
                onHover={setHoveredId}
                hovered={hoveredId === node.id}
              />
            );
          })}
        </svg>
      </div>

      <div style={{ textAlign: "center", padding: "8px", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
        Drag to pan {String.fromCharCode(8226)} Scroll to zoom {String.fromCharCode(8226)} {layout.nodes.length} nodes
      </div>
    </div>
  );
}
