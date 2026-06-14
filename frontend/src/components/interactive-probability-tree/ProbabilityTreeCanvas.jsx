/**
 * ProbabilityTreeCanvas — SVG layer for InteractiveProbabilityTree.
 * Renders edges (with probability labels / hidden inputs) and nodes.
 * Extracted from InteractiveProbabilityTree.jsx — pure-prop child; no state.
 */
export default function ProbabilityTreeCanvas({
  edges,
  nodes,
  answers,
  handleChange,
  readOnly,
  svgWidth,
  svgHeight,
}) {
  return (
    <svg width={svgWidth} height={svgHeight}>
      <rect x={0} y={0} width={svgWidth} height={svgHeight}
        style={{ fill: 'var(--input-bg)' }} rx={8} />

      {/* Edges */}
      {edges.map((edge, i) => {
        const fromNode = nodes.find(n => n.id === edge.from);
        const toNode = nodes.find(n => n.id === edge.to);
        if (!fromNode || !toNode) return null;

        const mx = (fromNode.x + toNode.x) / 2;
        const my = (fromNode.y + toNode.y) / 2 - 8;

        return (
          <g key={`edge-${i}`}>
            <line
              x1={fromNode.x + 20}
              y1={fromNode.y}
              x2={toNode.x - 20}
              y2={toNode.y}
              stroke="rgba(99, 102, 241, 0.4)"
              strokeWidth={2}
            />
            {/* Probability label on edge */}
            {edge.hidden ? (
              <foreignObject x={mx - 30} y={my - 10} width={60} height={24}>
                <input
                  type="text"
                  value={answers[edge.pathKey] || ''}
                  onChange={(e) => handleChange(edge.pathKey, e.target.value)}
                  disabled={readOnly}
                  placeholder="?"
                  style={edgeInputStyle}
                />
              </foreignObject>
            ) : (
              <text x={mx} y={my} textAnchor="middle" fontSize={11}
                fontWeight="600" style={{ fill: '#f59e0b' }}>
                {edge.probability}
              </text>
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {nodes.map((node) => {
        const isRoot = node.level === 0;
        const isLeaf = !node.branches || node.branches.length === 0;
        const bgColor = isRoot ? '#6366f1' : isLeaf ? '#10b981' : '#8b5cf6';

        return (
          <g key={`node-${node.id}`}>
            <rect
              x={node.x - 20}
              y={node.y - 14}
              width={40}
              height={28}
              rx={6}
              fill={bgColor}
              opacity={0.85}
            />
            <text
              x={node.x}
              y={node.y + 4}
              textAnchor="middle"
              fontSize={12}
              fontWeight="bold"
              fill="#fff"
            >
              {node.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const edgeInputStyle = {
  width: '56px',
  padding: '2px 4px',
  border: '1px solid #f59e0b',
  borderRadius: '4px',
  fontSize: '11px',
  fontWeight: '600',
  textAlign: 'center',
  background: 'rgba(245, 158, 11, 0.1)',
  color: '#f59e0b',
};
