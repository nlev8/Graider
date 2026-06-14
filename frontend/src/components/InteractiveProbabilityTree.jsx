import { useState } from 'react';
import ProbabilityTreeCanvas from './interactive-probability-tree/ProbabilityTreeCanvas.jsx';

/**
 * InteractiveProbabilityTree - Branching probability diagram.
 * Students fill in missing probabilities or outcomes.
 * Supports 2-3 levels of branching. Grades 7-12.
 */
export default function InteractiveProbabilityTree({
  tree = null,
  answers = {},
  onChange,
  correctAnswers = null,
  readOnly = false
}) {
  /*
    tree structure:
    {
      label: 'Start',
      branches: [
        {
          label: 'Heads',
          probability: '1/2',
          hidden: false,
          branches: [
            { label: 'Heads', probability: '1/2', hidden: false },
            { label: 'Tails', probability: '1/2', hidden: true }
          ]
        },
        { label: 'Tails', probability: '1/2', hidden: false, branches: [...] }
      ]
    }
  */

  const defaultTree = tree || {
    label: 'Start',
    branches: [
      {
        label: 'H', probability: '1/2', hidden: false,
        branches: [
          { label: 'H', probability: '1/2', hidden: false },
          { label: 'T', probability: '1/2', hidden: false }
        ]
      },
      {
        label: 'T', probability: '1/2', hidden: false,
        branches: [
          { label: 'H', probability: '1/2', hidden: false },
          { label: 'T', probability: '1/2', hidden: true }
        ]
      }
    ]
  };

  const svgWidth = 560;
  const svgHeight = 360;

  const handleChange = (key, value) => {
    if (readOnly) return;
    onChange?.({ ...answers, [key]: value });
  };

  // Flatten tree to get layout positions
  const nodes = [];
  const edges = [];
  let nodeId = 0;

  const layoutTree = (node, level, yStart, yEnd, parentId = null) => {
    const id = nodeId++;
    const x = 60 + level * 160;
    const y = (yStart + yEnd) / 2;
    nodes.push({ ...node, id, x, y, level });

    if (parentId !== null) {
      edges.push({ from: parentId, to: id, probability: node.probability, hidden: node.hidden, pathKey: `prob_${id}` });
    }

    if (node.branches && node.branches.length > 0) {
      const branchCount = node.branches.length;
      const segmentH = (yEnd - yStart) / branchCount;
      node.branches.forEach((child, i) => {
        layoutTree(child, level + 1, yStart + i * segmentH, yStart + (i + 1) * segmentH, id);
      });
    }
  };

  layoutTree(defaultTree, 0, 30, svgHeight - 30);

  // Compute outcomes at leaf nodes
  const getOutcomePaths = () => {
    const paths = [];
    const walk = (node, path, probPath) => {
      const current = [...path, node.label];
      const currentProb = node.probability ? [...probPath, node.probability] : probPath;
      if (!node.branches || node.branches.length === 0) {
        paths.push({ outcome: current.join(', '), probabilities: currentProb });
      } else {
        node.branches.forEach(child => walk(child, current, currentProb));
      }
    };
    walk(defaultTree, [], []);
    return paths;
  };

  const outcomes = getOutcomePaths();

  return (
    <div style={styles.container}>
      <ProbabilityTreeCanvas
        edges={edges}
        nodes={nodes}
        answers={answers}
        handleChange={handleChange}
        readOnly={readOnly}
        svgWidth={svgWidth}
        svgHeight={svgHeight}
      />

      {/* Outcomes table */}
      {outcomes.length > 0 && (
        <div style={styles.outcomesWrap}>
          <div style={styles.outcomesTitle}>Outcomes:</div>
          <div style={styles.outcomesGrid}>
            {outcomes.map((o, i) => (
              <div key={i} style={styles.outcomeRow}>
                <span style={styles.outcomePath}>{o.outcome}</span>
                <span style={styles.outcomeProb}>
                  P = {o.probabilities.join(' ' + String.fromCharCode(215) + ' ')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Answer input for total probability question */}
      {Object.keys(answers).some(k => k.startsWith('total_') || k.startsWith('outcome_')) && (
        <div style={styles.answerSection}>
          <label style={styles.label}>Final Answer:</label>
          <input
            type="text"
            value={answers.final || ''}
            onChange={(e) => handleChange('final', e.target.value)}
            disabled={readOnly}
            placeholder="e.g. 1/4"
            style={styles.finalInput}
          />
          {correctAnswers?.final && (
            <span style={styles.correctHint}>{correctAnswers.final}</span>
          )}
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '12px',
  },
  outcomesWrap: {
    width: '100%',
    maxWidth: '500px',
  },
  outcomesTitle: {
    fontSize: '0.9rem',
    fontWeight: '600',
    color: 'var(--text-primary)',
    marginBottom: '6px',
  },
  outcomesGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  outcomeRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '4px 10px',
    background: 'var(--input-bg)',
    borderRadius: '4px',
    fontSize: '0.85rem',
  },
  outcomePath: {
    color: 'var(--text-primary)',
    fontWeight: '500',
  },
  outcomeProb: {
    color: 'var(--text-muted)',
    fontFamily: 'monospace',
  },
  answerSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    alignItems: 'center',
  },
  label: {
    fontSize: '0.9rem',
    fontWeight: '500',
    color: 'var(--text-secondary)',
  },
  finalInput: {
    width: '120px',
    padding: '10px',
    border: '2px solid #6366f1',
    borderRadius: '6px',
    fontSize: '1.1rem',
    fontWeight: '600',
    textAlign: 'center',
    background: 'var(--input-bg)',
    color: 'var(--text-primary)',
  },
  correctHint: {
    fontSize: '0.85rem',
    color: '#22c55e',
    fontWeight: '500',
  },
};
