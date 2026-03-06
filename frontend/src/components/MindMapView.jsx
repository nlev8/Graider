import React, { useState, useRef, useEffect, useMemo, useCallback } from "react";

/**
 * MindMapView — Collapsible tree mind map renderer.
 * Starts collapsed (root + first-level visible). Click nodes to expand/collapse children.
 * Supports pan (drag), zoom (scroll), and reset.
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
  return Math.min(text.length * fontSize * 0.55, 200);
}

// Assign a unique numeric id and branchIndex to every node in the tree
function tagTree(node, counter, branchIndex) {
  var id = counter.val++;
  var children = (node.children || []).map(function(child, ci) {
    return tagTree(child, counter, branchIndex === -1 ? ci : branchIndex);
  });
  return {
    id: id,
    name: node.name,
    children: children,
    branchIndex: branchIndex,
    hasChildren: children.length > 0,
  };
}

// Layout config
var NODE_H = 36;         // Height per node row
var NODE_GAP_Y = 6;      // Vertical gap between sibling nodes
var LEVEL_GAP_X = 200;   // Horizontal gap between levels
var ROOT_FONT = 15;
var BRANCH_FONT = 13;
var LEAF_FONT = 11;

// Recursively compute positions in a left-to-right tree layout
// Returns { positioned: [...], edges: [...], totalHeight }
function layoutCollapsible(node, expanded, depth, x, yStart) {
  var isRoot = depth === 0;
  var fontSize = isRoot ? ROOT_FONT : depth === 1 ? BRANCH_FONT : LEAF_FONT;
  var padding = isRoot ? 18 : depth === 1 ? 12 : 8;
  var maxWidth = isRoot ? 180 : depth === 1 ? 160 : 140;

  // Word wrap
  var words = node.name.split(" ");
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

  var isExpanded = !!expanded[node.id];
  var showChildren = node.hasChildren && isExpanded;

  if (!showChildren) {
    // Leaf or collapsed — single row
    var positioned = [{
      id: node.id,
      text: node.name,
      x: x,
      y: yStart + boxHeight / 2,
      depth: depth,
      branchIndex: node.branchIndex,
      hasChildren: node.hasChildren,
      isExpanded: isExpanded,
      lines: lines,
      fontSize: fontSize,
      padding: padding,
      boxWidth: boxWidth,
      boxHeight: boxHeight,
      lineHeight: lineHeight,
      textHeight: textHeight,
    }];
    return { positioned: positioned, edges: [], totalHeight: boxHeight };
  }

  // Layout children
  var childResults = [];
  var childTotalHeight = 0;
  node.children.forEach(function(child, ci) {
    if (ci > 0) childTotalHeight += NODE_GAP_Y;
    var result = layoutCollapsible(child, expanded, depth + 1, x + LEVEL_GAP_X, yStart + childTotalHeight);
    childResults.push({ result: result, yOffset: childTotalHeight });
    childTotalHeight += result.totalHeight;
  });

  // Parent centered on children block
  var parentHeight = Math.max(boxHeight, childTotalHeight);
  var parentY = yStart + childTotalHeight / 2;

  var parentNode = {
    id: node.id,
    text: node.name,
    x: x,
    y: parentY,
    depth: depth,
    branchIndex: node.branchIndex,
    hasChildren: node.hasChildren,
    isExpanded: isExpanded,
    lines: lines,
    fontSize: fontSize,
    padding: padding,
    boxWidth: boxWidth,
    boxHeight: boxHeight,
    lineHeight: lineHeight,
    textHeight: textHeight,
  };

  var allPositioned = [parentNode];
  var allEdges = [];

  childResults.forEach(function(cr) {
    cr.result.positioned.forEach(function(p) { allPositioned.push(p); });
    cr.result.edges.forEach(function(e) { allEdges.push(e); });
    // Edge from parent to first node in child subtree (the child root)
    var childRoot = cr.result.positioned[0];
    allEdges.push({
      from: parentNode,
      to: childRoot,
      branchIndex: childRoot.branchIndex,
    });
  });

  return { positioned: allPositioned, edges: allEdges, totalHeight: parentHeight };
}

function CurvedEdge({ from, to, color }) {
  var x1 = from.x + from.boxWidth / 2;
  var y1 = from.y;
  var x2 = to.x - to.boxWidth / 2;
  var y2 = to.y;
  var midX = (x1 + x2) / 2;
  var d = "M " + x1 + " " + y1 + " C " + midX + " " + y1 + ", " + midX + " " + y2 + ", " + x2 + " " + y2;

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

function NodeBox({ node, color, onToggle, onHover, hovered }) {
  var isRoot = node.depth === 0;
  var indicatorRadius = 9;

  return (
    <g
      transform={"translate(" + node.x + "," + node.y + ")"}
      onMouseEnter={function() { onHover(node.id); }}
      onMouseLeave={function() { onHover(null); }}
      onClick={function(e) {
        e.stopPropagation();
        if (node.hasChildren) onToggle(node.id);
      }}
      style={{ cursor: node.hasChildren ? "pointer" : "default" }}
    >
      {/* Shadow for root */}
      {isRoot && (
        <rect
          x={-node.boxWidth / 2 + 2}
          y={-node.boxHeight / 2 + 2}
          width={node.boxWidth}
          height={node.boxHeight}
          rx={16}
          fill="rgba(0,0,0,0.1)"
        />
      )}
      {/* Background */}
      <rect
        x={-node.boxWidth / 2}
        y={-node.boxHeight / 2}
        width={node.boxWidth}
        height={node.boxHeight}
        rx={isRoot ? 16 : 10}
        fill={isRoot ? color : (hovered ? color + "30" : color + "18")}
        stroke={color}
        strokeWidth={isRoot ? 0 : hovered ? 2 : 1}
        strokeOpacity={isRoot ? 0 : 0.5}
      />
      {/* Text */}
      {node.lines.map(function(line, li) {
        return (
          <text
            key={li}
            x={0}
            y={-node.textHeight / 2 + (li + 0.75) * node.lineHeight}
            textAnchor="middle"
            fill={isRoot ? "white" : "var(--text-primary)"}
            fontSize={node.fontSize}
            fontWeight={isRoot ? 700 : node.depth === 1 ? 600 : 400}
            fontFamily="system-ui, -apple-system, sans-serif"
            style={{ pointerEvents: "none" }}
          >
            {line}
          </text>
        );
      })}
      {/* Expand/collapse indicator */}
      {node.hasChildren && (
        <g transform={"translate(" + (node.boxWidth / 2 + 2) + ",0)"}>
          <circle
            r={indicatorRadius}
            fill={hovered ? color + "30" : "var(--bg-primary)"}
            stroke={color}
            strokeWidth={1.5}
          />
          <text
            x={0}
            y={1}
            textAnchor="middle"
            dominantBaseline="middle"
            fill={color}
            fontSize={13}
            fontWeight={700}
            fontFamily="system-ui, -apple-system, sans-serif"
            style={{ pointerEvents: "none" }}
          >
            {node.isExpanded ? String.fromCharCode(8722) : "+"}
          </text>
        </g>
      )}
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

  // Tag tree with ids
  var tagged = useMemo(function() {
    if (!tree || !tree.name) return null;
    return tagTree(tree, { val: 0 }, -1);
  }, [tree]);

  // Start with root expanded (shows first-level branches)
  var [expanded, setExpanded] = useState(function() {
    return { 0: true };
  });

  // Reset expanded state when data changes
  useEffect(function() {
    setExpanded({ 0: true });
    setPan({ x: 0, y: 0 });
    setZoom(1);
  }, [tree]);

  var toggleNode = useCallback(function(id) {
    setExpanded(function(prev) {
      var copy = Object.assign({}, prev);
      if (copy[id]) {
        delete copy[id];
      } else {
        copy[id] = true;
      }
      return copy;
    });
  }, []);

  // Expand all / collapse all
  var expandAll = useCallback(function() {
    if (!tagged) return;
    var allIds = {};
    function collect(node) {
      if (node.hasChildren) {
        allIds[node.id] = true;
        node.children.forEach(collect);
      }
    }
    collect(tagged);
    setExpanded(allIds);
  }, [tagged]);

  var collapseAll = useCallback(function() {
    setExpanded({ 0: true });
  }, []);

  if (!tagged) {
    return (
      <div style={{ padding: "20px", color: "var(--text-secondary)", fontStyle: "italic" }}>
        No mind map data available.
      </div>
    );
  }

  var layout = layoutCollapsible(tagged, expanded, 0, 0, 0);

  // Compute SVG viewbox from node positions
  var bounds = useMemo(function() {
    var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    layout.positioned.forEach(function(n) {
      var halfW = n.boxWidth / 2 + 20; // account for +/- indicator
      minX = Math.min(minX, n.x - halfW);
      maxX = Math.max(maxX, n.x + halfW);
      minY = Math.min(minY, n.y - n.boxHeight / 2);
      maxY = Math.max(maxY, n.y + n.boxHeight / 2);
    });
    var pad = 40;
    return {
      x: minX - pad,
      y: minY - pad,
      width: maxX - minX + pad * 2,
      height: maxY - minY + pad * 2,
    };
  }, [layout]);

  // Count visible vs total
  var totalNodes = useMemo(function() {
    var count = 0;
    function walk(n) { count++; n.children.forEach(walk); }
    walk(tagged);
    return count;
  }, [tagged]);

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

  var smallBtnStyle = {
    height: "30px", borderRadius: "8px", border: "1px solid var(--border)",
    background: "var(--bg-primary)", cursor: "pointer", fontSize: "0.75rem",
    padding: "0 8px", display: "flex", alignItems: "center", color: "var(--text-primary)",
  };

  return (
    <div style={{ position: "relative" }}>
      {/* Controls */}
      <div style={{ position: "absolute", top: "10px", right: "10px", zIndex: 10, display: "flex", gap: "4px" }}>
        <button
          onClick={function() { setZoom(function(z) { return Math.min(3, z * 1.2); }); }}
          style={{ width: "30px", height: "30px", borderRadius: "8px", border: "1px solid var(--border)", background: "var(--bg-primary)", cursor: "pointer", fontSize: "1rem", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-primary)" }}
        >+</button>
        <button
          onClick={function() { setZoom(function(z) { return Math.max(0.3, z * 0.8); }); }}
          style={{ width: "30px", height: "30px", borderRadius: "8px", border: "1px solid var(--border)", background: "var(--bg-primary)", cursor: "pointer", fontSize: "1rem", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-primary)" }}
        >{String.fromCharCode(8722)}</button>
        <button onClick={expandAll} style={smallBtnStyle}>Expand All</button>
        <button onClick={collapseAll} style={smallBtnStyle}>Collapse</button>
        <button
          onClick={function() { setZoom(1); setPan({ x: 0, y: 0 }); }}
          style={smallBtnStyle}
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
            var color = edge.from.depth === 0
              ? BRANCH_COLORS[edge.branchIndex % BRANCH_COLORS.length]
              : BRANCH_COLORS[edge.branchIndex % BRANCH_COLORS.length];
            return <CurvedEdge key={"e" + i} from={edge.from} to={edge.to} color={color} />;
          })}

          {/* Nodes */}
          {layout.positioned.map(function(node) {
            var color = node.depth === 0
              ? "#8b5cf6"
              : BRANCH_COLORS[node.branchIndex % BRANCH_COLORS.length];
            return (
              <NodeBox
                key={node.id}
                node={node}
                color={color}
                onToggle={toggleNode}
                onHover={setHoveredId}
                hovered={hoveredId === node.id}
              />
            );
          })}
        </svg>
      </div>

      <div style={{ textAlign: "center", padding: "8px", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
        Click nodes to expand/collapse {String.fromCharCode(8226)} Drag to pan {String.fromCharCode(8226)} Scroll to zoom {String.fromCharCode(8226)} {layout.positioned.length} of {totalNodes} nodes visible
      </div>
    </div>
  );
}
