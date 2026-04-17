"""
Fairness Analysis Engine
Inspects CSV datasets for bias across protected attributes.
"""
import csv
import io
import math
from collections import Counter, defaultdict


# Keywords to auto-detect protected/sensitive attributes
PROTECTED_KEYWORDS = [
    'gender', 'sex', 'race', 'ethnicity', 'ethnic', 'age', 'religion',
    'disability', 'marital', 'married', 'nationality', 'national_origin',
    'skin', 'color', 'colour', 'orientation', 'pregnant', 'veteran',
    'citizen', 'immigration', 'language', 'caste', 'tribe', 'indigenous',
]

# Keywords to auto-detect target/outcome columns
TARGET_KEYWORDS = [
    'approved', 'accepted', 'hired', 'selected', 'admitted', 'granted',
    'result', 'outcome', 'decision', 'label', 'target', 'prediction',
    'predicted', 'class', 'default', 'loan_status', 'status',
    'pass', 'fail', 'positive', 'negative', 'recidivism', 'score',
]


def detect_protected_attributes(columns):
    """Auto-detect columns that likely represent protected attributes."""
    protected = []
    for col in columns:
        col_lower = col.lower().strip().replace(' ', '_')
        for keyword in PROTECTED_KEYWORDS:
            if keyword in col_lower:
                protected.append(col)
                break
    return protected


def detect_target_column(columns):
    """Auto-detect the target/outcome column."""
    for col in columns:
        col_lower = col.lower().strip().replace(' ', '_')
        for keyword in TARGET_KEYWORDS:
            if keyword in col_lower:
                return col
    return None


def parse_csv_data(file_content):
    """Parse CSV content into a list of dictionaries."""
    if isinstance(file_content, bytes):
        file_content = file_content.decode('utf-8-sig')
    
    reader = csv.DictReader(io.StringIO(file_content))
    rows = list(reader)
    columns = reader.fieldnames or []
    return rows, columns


def is_positive_outcome(value):
    """Determine if a value represents a positive outcome."""
    if value is None:
        return False
    val = str(value).strip().lower()
    positive_values = {'1', 'yes', 'true', 'approved', 'accepted', 'hired',
                       'selected', 'admitted', 'granted', 'pass', 'positive', 'y'}
    return val in positive_values


def compute_group_distributions(rows, attribute):
    """Compute the distribution of values for a given attribute."""
    counter = Counter()
    for row in rows:
        val = row.get(attribute, '').strip()
        if val:
            counter[val] += 1
    total = sum(counter.values())
    distribution = {}
    for val, count in counter.most_common():
        distribution[val] = {
            'count': count,
            'percentage': round((count / total) * 100, 2) if total > 0 else 0
        }
    return distribution


def compute_outcome_rates(rows, attribute, target_col):
    """Compute positive outcome rates for each group within an attribute."""
    group_totals = defaultdict(int)
    group_positives = defaultdict(int)

    for row in rows:
        group = row.get(attribute, '').strip()
        outcome = row.get(target_col, '').strip()
        if group and outcome:
            group_totals[group] += 1
            if is_positive_outcome(outcome):
                group_positives[group] += 1

    rates = {}
    for group in group_totals:
        total = group_totals[group]
        pos = group_positives[group]
        rates[group] = {
            'total': total,
            'positive': pos,
            'negative': total - pos,
            'rate': round((pos / total) * 100, 2) if total > 0 else 0,
        }
    return rates


def compute_demographic_parity(outcome_rates):
    """
    Demographic Parity: measures if positive outcome rates are equal across groups.
    Ratio of min rate to max rate. 1.0 = perfect parity, < 0.8 = concern.
    """
    if not outcome_rates:
        return None, {}
    rates = [v['rate'] for v in outcome_rates.values() if v['total'] > 0]
    if not rates or max(rates) == 0:
        return None, {}
    ratio = min(rates) / max(rates) if max(rates) > 0 else 1.0
    return round(ratio, 4), {
        'min_rate': min(rates),
        'max_rate': max(rates),
        'min_group': [k for k, v in outcome_rates.items() if v['rate'] == min(rates)][0],
        'max_group': [k for k, v in outcome_rates.items() if v['rate'] == max(rates)][0],
    }


def compute_disparate_impact(outcome_rates):
    """
    Disparate Impact Ratio: P(positive|unprivileged) / P(positive|privileged).
    Uses min/max rates as proxy. < 0.8 = potential discrimination (4/5ths rule).
    """
    if not outcome_rates:
        return None, {}
    rates = [v['rate'] for v in outcome_rates.values() if v['total'] > 0]
    if not rates or max(rates) == 0:
        return None, {}
    ratio = min(rates) / max(rates) if max(rates) > 0 else 1.0
    return round(ratio, 4), {
        'rule': '4/5ths (80%) Rule',
        'threshold': 0.8,
        'passed': ratio >= 0.8,
    }


def compute_statistical_parity_difference(outcome_rates):
    """
    Statistical Parity Difference: |max_rate - min_rate|.
    0 = perfect fairness, > 0.1 = potentially unfair.
    """
    if not outcome_rates:
        return None, {}
    rates = [v['rate'] for v in outcome_rates.values() if v['total'] > 0]
    if not rates:
        return None, {}
    diff = abs(max(rates) - min(rates))
    return round(diff, 4), {
        'max_rate': max(rates),
        'min_rate': min(rates),
        'difference_percentage': round(diff, 2),
    }


def compute_group_size_ratio(distribution):
    """
    Group Size Ratio: measures representation balance.
    Ratio of smallest to largest group. 1.0 = perfectly balanced.
    """
    if not distribution:
        return None, {}
    counts = [v['count'] for v in distribution.values()]
    if not counts or max(counts) == 0:
        return None, {}
    ratio = min(counts) / max(counts)
    return round(ratio, 4), {
        'smallest_group_size': min(counts),
        'largest_group_size': max(counts),
    }


def determine_severity(fairness_score):
    """Determine bias severity based on overall fairness score."""
    if fairness_score >= 85:
        return 'low'
    elif fairness_score >= 65:
        return 'medium'
    elif fairness_score >= 40:
        return 'high'
    else:
        return 'critical'


def generate_recommendations(metrics_data):
    """Generate context-aware bias mitigation recommendations."""
    recommendations = []

    for attr_data in metrics_data.values():
        attr = attr_data.get('attribute', 'Unknown')
        dp = attr_data.get('demographic_parity', {})
        di = attr_data.get('disparate_impact', {})
        spd = attr_data.get('statistical_parity_difference', {})
        gsr = attr_data.get('group_size_ratio', {})

        # Check Disparate Impact
        if di.get('value') is not None and di['value'] < 0.8:
            recommendations.append({
                'severity': 'high',
                'attribute': attr,
                'metric': 'Disparate Impact',
                'title': f'Significant disparate impact detected for "{attr}"',
                'description': f'The disparate impact ratio is {di["value"]:.2f}, below the 4/5ths (0.80) threshold. '
                               f'This indicates that outcomes are not distributed fairly across groups.',
                'actions': [
                    'Review the dataset for historical bias in this attribute',
                    'Consider reweighing or resampling the data to balance group representation',
                    'Implement in-processing fairness constraints during model training',
                    'Apply post-processing calibration to equalize outcome rates',
                ]
            })

        # Check Statistical Parity
        if spd.get('value') is not None and spd['value'] > 15:
            recommendations.append({
                'severity': 'medium',
                'attribute': attr,
                'metric': 'Statistical Parity',
                'title': f'Outcome rate gap detected for "{attr}"',
                'description': f'There is a {spd["value"]:.1f}% difference in positive outcome rates between groups.',
                'actions': [
                    'Investigate why certain groups have lower outcome rates',
                    'Check for proxy variables that may correlate with this attribute',
                    'Consider using outcome-balanced sampling techniques',
                ]
            })

        # Check Group Representation
        if gsr.get('value') is not None and gsr['value'] < 0.5:
            recommendations.append({
                'severity': 'medium',
                'attribute': attr,
                'metric': 'Group Representation',
                'title': f'Imbalanced representation in "{attr}"',
                'description': f'The smallest group is only {gsr["value"]:.0%} the size of the largest group. '
                               f'Underrepresented groups may lead to unreliable predictions.',
                'actions': [
                    'Collect more data for underrepresented groups',
                    'Use oversampling techniques (e.g., SMOTE) to balance the dataset',
                    'Apply stratified sampling to ensure fair evaluation',
                ]
            })

    if not recommendations:
        recommendations.append({
            'severity': 'low',
            'attribute': 'Overall',
            'metric': 'All Metrics',
            'title': 'No significant bias detected',
            'description': 'The dataset appears to be reasonably fair across all protected attributes and metrics. '
                           'Continue monitoring as data evolves.',
            'actions': [
                'Maintain regular bias audits as new data is collected',
                'Document your fairness evaluation process for compliance',
                'Consider intersectional analysis for deeper insights',
            ]
        })

    return recommendations


def run_full_analysis(file_content, protected_attrs=None, target_col=None):
    """
    Run the complete bias analysis pipeline on a CSV dataset.
    
    Returns a dictionary with:
    - dataset_info: basic stats about the dataset
    - protected_attributes: detected sensitive columns
    - target_column: detected outcome column
    - metrics: per-attribute fairness metrics
    - overall_score: 0-100 fairness score
    - severity: low/medium/high/critical
    - recommendations: actionable suggestions
    """
    rows, columns = parse_csv_data(file_content)

    if not rows:
        return {'error': 'Dataset is empty or could not be parsed.'}

    # Auto-detect if not provided
    if not protected_attrs:
        protected_attrs = detect_protected_attributes(columns)
    if not target_col:
        target_col = detect_target_column(columns)

    dataset_info = {
        'row_count': len(rows),
        'column_count': len(columns),
        'columns': columns,
        'protected_attributes': protected_attrs,
        'target_column': target_col,
    }

    if not protected_attrs:
        return {
            'dataset_info': dataset_info,
            'error': 'No protected attributes detected. Please specify which columns represent sensitive attributes.',
            'metrics': {},
            'overall_score': 0,
            'severity': 'medium',
            'recommendations': [{
                'severity': 'medium',
                'attribute': 'N/A',
                'metric': 'Detection',
                'title': 'No protected attributes found',
                'description': 'Could not auto-detect protected attributes. Column names should include keywords like gender, race, age, etc.',
                'actions': ['Rename columns to clearly indicate sensitive attributes', 'Manually specify protected attributes'],
            }],
        }

    metrics_data = {}
    all_scores = []

    for attr in protected_attrs:
        distribution = compute_group_distributions(rows, attr)

        attr_metrics = {
            'attribute': attr,
            'distribution': distribution,
            'group_count': len(distribution),
        }

        # Group size ratio
        gsr_val, gsr_details = compute_group_size_ratio(distribution)
        attr_metrics['group_size_ratio'] = {'value': gsr_val, 'details': gsr_details}
        if gsr_val is not None:
            all_scores.append(min(gsr_val / 1.0 * 100, 100))

        # If we have a target column, compute outcome-based metrics
        if target_col:
            outcome_rates = compute_outcome_rates(rows, attr, target_col)
            attr_metrics['outcome_rates'] = outcome_rates

            # Demographic Parity
            dp_val, dp_details = compute_demographic_parity(outcome_rates)
            attr_metrics['demographic_parity'] = {'value': dp_val, 'details': dp_details}
            if dp_val is not None:
                all_scores.append(min(dp_val / 1.0 * 100, 100))

            # Disparate Impact
            di_val, di_details = compute_disparate_impact(outcome_rates)
            attr_metrics['disparate_impact'] = {'value': di_val, 'details': di_details}
            if di_val is not None:
                all_scores.append(min(di_val / 0.8 * 100, 100))  # normalize to 80% threshold

            # Statistical Parity Difference
            spd_val, spd_details = compute_statistical_parity_difference(outcome_rates)
            attr_metrics['statistical_parity_difference'] = {'value': spd_val, 'details': spd_details}
            if spd_val is not None:
                # Lower is better; 0 = 100%, 50+ = 0%
                score = max(0, 100 - (spd_val * 2))
                all_scores.append(score)

        metrics_data[attr] = attr_metrics

    # Calculate overall fairness score
    overall_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 50.0
    severity = determine_severity(overall_score)

    # Generate recommendations
    recommendations = generate_recommendations(metrics_data)

    return {
        'dataset_info': dataset_info,
        'metrics': metrics_data,
        'overall_score': overall_score,
        'severity': severity,
        'recommendations': recommendations,
    }
