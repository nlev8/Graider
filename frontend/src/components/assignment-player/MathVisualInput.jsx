import InteractiveNumberLine from '../InteractiveNumberLine';
import InteractiveCoordinatePlane from '../InteractiveCoordinatePlane';
import InteractiveGeometry from '../InteractiveGeometry';
import InteractiveBoxPlot from '../InteractiveBoxPlot';
import InteractiveFunctionGraph from '../InteractiveFunctionGraph';
import InteractiveDotPlot from '../InteractiveDotPlot';
import InteractiveStemAndLeaf from '../InteractiveStemAndLeaf';
import InteractiveUnitCircle from '../InteractiveUnitCircle';
import InteractiveTransformations from '../InteractiveTransformations';
import InteractiveFractionModel from '../InteractiveFractionModel';
import InteractiveProbabilityTree from '../InteractiveProbabilityTree';
import InteractiveTapeDiagram from '../InteractiveTapeDiagram';
import InteractiveVennDiagram from '../InteractiveVennDiagram';
import InteractiveProtractor from '../InteractiveProtractor';

/**
 * Question types rendered by MathVisualInput. QuestionRenderer dispatches on
 * this list; every other type falls through to ChoiceTextInput. The entries
 * mirror the original renderInput switch case labels exactly (CQ wave-4
 * split of AssignmentPlayer.jsx — case bodies relocated verbatim).
 */
export const MATH_VISUAL_TYPES = [
  'number_line', 'coordinate_plane',
  'geometry', 'triangle', 'rectangle', 'regular_polygon', 'circle',
  'trapezoid', 'parallelogram', 'rectangular_prism', 'cylinder', 'cone',
  'pyramid', 'sphere', 'similarity', 'pythagorean', 'angles', 'trig',
  'box_plot', 'function_graph', 'dot_plot', 'stem_and_leaf', 'unit_circle',
  'transformations', 'fraction_model', 'probability_tree', 'tape_diagram',
  'venn_diagram', 'protractor', 'angle_protractor',
];

/**
 * MathVisualInput - renders the interactive math/visual input component for a
 * question (number lines, coordinate planes, geometry, plots, manipulatives).
 */
export default function MathVisualInput({
  question,
  qType,
  answer,
  onAnswer,
  readOnly,
  showAnswer,
  inputKey,
  onInputFocus,
}) {
  switch (qType) {
    case 'number_line':
      return (
        <InteractiveNumberLine
          minVal={question.min_val ?? -10}
          maxVal={question.max_val ?? 10}
          points={answer || []}
          onChange={onAnswer}
          correctPoints={showAnswer ? question.points_to_plot : null}
          readOnly={readOnly}
        />
      );

    case 'coordinate_plane':
      return (
        <InteractiveCoordinatePlane
          xRange={question.x_range || [-6, 6]}
          yRange={question.y_range || [-6, 6]}
          points={answer || []}
          labels={question.point_labels || []}
          onChange={onAnswer}
          correctPoints={showAnswer ? question.points_to_plot : null}
          readOnly={readOnly}
        />
      );

    case 'geometry':
    case 'triangle':
    case 'rectangle':
    case 'regular_polygon':
    case 'circle':
    case 'trapezoid':
    case 'parallelogram':
    case 'rectangular_prism':
    case 'cylinder':
    case 'cone':
    case 'pyramid':
    case 'sphere':
    case 'similarity':
    case 'pythagorean':
    case 'angles':
    case 'trig':
      return (
        <InteractiveGeometry
          type={qType === 'geometry' ? 'triangle' : qType}
          base={question.base || 6}
          height={question.height || 4}
          width={question.width}
          radius={question.radius}
          topBase={question.top_base}
          mode={question.mode || 'area'}
          sides={question.sides}
          sideLength={question.side_length}
          sideA={question.side_a}
          sideB={question.side_b}
          sideC={question.side_c}
          angle1={question.angle1}
          angle2={question.angle2}
          missingAngle={question.missing_angle}
          theta={question.theta}
          trigFunc={question.trig_func}
          missingSide={question.missing_side}
          slantHeight={question.slant_height}
          scale={question.scale}
          answer={answer || ''}
          onChange={onAnswer}
          correctAnswer={showAnswer ? question.answer : null}
          readOnly={readOnly}
          onInputFocus={(ref, subfield, mode) => onInputFocus?.(ref, inputKey + '-' + subfield, mode)}
        />
      );

    case 'box_plot':
      return (
        <InteractiveBoxPlot
          data={question.data || [[50, 60, 70, 80, 90]]}
          labels={question.data_labels}
          answers={answer || {}}
          onChange={onAnswer}
          correctAnswers={showAnswer ? question.expected_values : null}
          readOnly={readOnly}
        />
      );

    case 'function_graph':
      return (
        <InteractiveFunctionGraph
          xRange={question.x_range || [-10, 10]}
          yRange={question.y_range || [-10, 10]}
          expressions={answer || []}
          onChange={onAnswer}
          correctExpressions={showAnswer ? question.correct_expressions : null}
          readOnly={readOnly}
          maxExpressions={question.max_expressions || 3}
          onInputFocus={(ref, exprIdx, mode) => onInputFocus?.(ref, inputKey + '-expr' + exprIdx, mode)}
        />
      );

    case 'dot_plot':
      return (
        <InteractiveDotPlot
          categories={question.categories || []}
          minVal={question.min_val ?? 0}
          maxVal={question.max_val ?? 10}
          step={question.step ?? 1}
          dots={answer || {}}
          onChange={onAnswer}
          correctDots={showAnswer ? question.correct_dots : null}
          readOnly={readOnly}
          title={question.chart_title || ''}
        />
      );

    case 'stem_and_leaf':
      return (
        <InteractiveStemAndLeaf
          data={question.data || []}
          stems={question.stems || []}
          leaves={answer || {}}
          onChange={onAnswer}
          correctLeaves={showAnswer ? question.correct_leaves : null}
          readOnly={readOnly}
          title={question.chart_title || ''}
        />
      );

    case 'unit_circle':
      return (
        <InteractiveUnitCircle
          hiddenAngles={question.hidden_angles || []}
          hiddenValues={question.hidden_values || []}
          answers={answer || {}}
          onChange={onAnswer}
          correctAnswers={showAnswer ? question.correct_values : null}
          readOnly={readOnly}
          showRadians={question.show_radians !== false}
          showCoordinates={question.show_coordinates !== false}
        />
      );

    case 'transformations':
      return (
        <InteractiveTransformations
          originalVertices={question.original_vertices || [[1,1],[4,1],[4,3]]}
          transformationType={question.transformation_type || 'translation'}
          transformParams={question.transform_params || {}}
          userVertices={answer?.vertices || []}
          answer={answer?.answer || ''}
          onChange={onAnswer}
          correctVertices={showAnswer ? question.correct_vertices : null}
          correctAnswer={showAnswer ? question.answer : null}
          readOnly={readOnly}
          gridRange={question.grid_range || [-8, 8]}
          mode={question.mode || 'plot'}
        />
      );

    case 'fraction_model':
      return (
        <InteractiveFractionModel
          modelType={question.model_type || 'area'}
          denominator={question.denominator || 4}
          correctNumerator={showAnswer ? question.correct_numerator : null}
          shaded={answer?.shaded || []}
          answer={answer?.answer || ''}
          onChange={onAnswer}
          correctAnswer={showAnswer ? question.answer : null}
          readOnly={readOnly}
          showFractionInput={question.show_fraction_input !== false}
          compareFractions={question.compare_fractions || null}
        />
      );

    case 'probability_tree':
      return (
        <InteractiveProbabilityTree
          tree={question.tree || null}
          answers={answer || {}}
          onChange={onAnswer}
          correctAnswers={showAnswer ? question.correct_values : null}
          readOnly={readOnly}
        />
      );

    case 'tape_diagram':
      return (
        <InteractiveTapeDiagram
          tapes={question.tapes || []}
          answers={answer || {}}
          onChange={onAnswer}
          correctAnswers={showAnswer ? question.correct_values : null}
          readOnly={readOnly}
          title={question.chart_title || ''}
        />
      );

    case 'venn_diagram':
      return (
        <InteractiveVennDiagram
          sets={question.sets || 2}
          labels={question.set_labels || ['Set A', 'Set B']}
          regions={question.regions || {}}
          answers={answer || {}}
          onChange={onAnswer}
          correctAnswers={showAnswer ? question.correct_values : null}
          readOnly={readOnly}
          title={question.chart_title || ''}
          mode={question.mode || 'count'}
        />
      );

    case 'protractor':
    case 'angle_protractor':
      return (
        <InteractiveProtractor
          givenAngle={question.given_angle}
          targetAngle={question.target_angle}
          mode={question.mode || 'measure'}
          answer={typeof answer === 'object' ? answer?.answer || '' : answer || ''}
          userAngle={typeof answer === 'object' ? answer?.userAngle || 0 : 0}
          onChange={onAnswer}
          correctAnswer={showAnswer ? question.answer : null}
          readOnly={readOnly}
          showClassification={question.show_classification !== false}
        />
      );

    default:
      return null;
  }
}
