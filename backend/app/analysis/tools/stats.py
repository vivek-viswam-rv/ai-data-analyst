"""Statistical test tools for the statistics agent.

Each tool runs a real scipy/numpy computation, registers a `StatTest` in the
shared `ArtifactStore` (with `conclusion=""` and `caveats=[]` left for the
model to fill in later via `assemble`), and returns a small dict of numbers
the model can read and reason about. Tools never return raw arrays or rows.
"""

from typing import Any

import numpy as np
import pandas as pd
from langchain_core.tools import BaseTool, tool
from scipy import stats

from app.analysis.schemas import StatTest
from app.analysis.tools.common import (
    ArtifactStore,
    ToolError,
    num,
    require_column,
    require_numeric,
    safe_tool,
)

MIN_GROUP_SIZE = 3
MIN_OVERALL_N = 8
MAX_GROUPS = 10
MAX_CATEGORIES = 12


def build_tools(df: pd.DataFrame, store: ArtifactStore) -> list[BaseTool]:
    def register(
        *,
        name: str,
        columns: list[str],
        hypothesis: str,
        statistic: float | None,
        p_value: float | None,
        effect_size: float | None,
        effect_size_name: str | None,
        caveats: list[str] | None = None,
    ) -> str:
        test = StatTest(
            id="",
            name=name,
            columns=columns,
            hypothesis=hypothesis,
            statistic=num(statistic),
            p_value=num(p_value),
            effect_size=num(effect_size),
            effect_size_name=effect_size_name,
            conclusion="",
            caveats=list(caveats) if caveats else [],
        )
        test_id = store.add("test", test)
        store.get(test_id).id = test_id
        return test_id

    @tool
    @safe_tool
    def normality_test(column: str) -> dict:
        """Test whether a numeric column is normally distributed.

        Runs the Shapiro-Wilk test (n <= 5000) or D'Agostino K-squared test
        (n > 5000), and reports skew and kurtosis. Use this before deciding
        whether a parametric test is appropriate for a column.
        """
        return _normality_test(df, store, register, column)

    @tool
    @safe_tool
    def compare_groups(value_column: str, group_column: str) -> dict:
        """Compare a numeric column's mean/distribution across groups of a categorical column.

        Runs Welch's t-test + Mann-Whitney U for exactly two groups, or
        one-way ANOVA + Kruskal-Wallis for three or more groups. Groups with
        fewer than 3 observations are excluded; only the 10 largest groups
        are kept if there are more than 10.
        """
        return _compare_groups(df, store, register, value_column, group_column)

    @tool
    @safe_tool
    def correlation_test(column_a: str, column_b: str) -> dict:
        """Test linear (Pearson) and monotonic (Spearman) association between two numeric columns.

        Use this to check whether two numeric columns move together.
        """
        return _correlation_test(df, store, register, column_a, column_b)

    @tool
    @safe_tool
    def chi_square_test(column_a: str, column_b: str) -> dict:
        """Test independence between two categorical columns with a chi-square test.

        Builds a contingency table (capped at the 12 most frequent categories
        per column) and reports Cramer's V as the effect size.
        """
        return _chi_square_test(df, store, register, column_a, column_b)

    @tool
    @safe_tool
    def linear_regression(target: str, features: list[str]) -> dict:
        """Fit an ordinary least squares regression of a numeric target on numeric features.

        Reports R-squared, adjusted R-squared, the overall F-test, and a
        coefficients table (intercept + each feature) with t-stats and
        p-values. Features are capped at 8 and constant (zero-variance)
        features are dropped.
        """
        return _linear_regression(df, store, register, target, features)

    return [
        normality_test,
        compare_groups,
        correlation_test,
        chi_square_test,
        linear_regression,
    ]


# Implementations are kept as plain functions (wrapped by safe_tool via the
# closures above) so they're easy to unit test / reuse.


def _normality_test(
    df: pd.DataFrame,
    store: ArtifactStore,
    register: Any,
    column: str,
) -> dict:
    col = require_numeric(df, column)
    values = df[col].dropna()
    n = len(values)
    if n < MIN_OVERALL_N:
        raise ToolError(
            f"Not enough data to test normality of '{col}': {n} non-missing values, "
            f"need at least {MIN_OVERALL_N}."
        )
    if n <= 5000:
        name = "Shapiro-Wilk normality test"
        statistic, p_value = stats.shapiro(values)
    else:
        name = "D'Agostino K² normality test"
        statistic, p_value = stats.normaltest(values)
    skew = stats.skew(values)
    kurtosis = stats.kurtosis(values)
    hypothesis = f"H0: {col} is normally distributed"
    test_id = register(
        name=name,
        columns=[col],
        hypothesis=hypothesis,
        statistic=statistic,
        p_value=p_value,
        effect_size=None,
        effect_size_name=None,
    )
    return {
        "test_id": test_id,
        "statistic": num(statistic),
        "p_value": num(p_value),
        "skew": num(skew),
        "kurtosis": num(kurtosis),
        "n": n,
        "hypothesis": hypothesis,
        "reading": "p < 0.05 means the data significantly deviates from a normal distribution.",
    }


def _compare_groups(
    df: pd.DataFrame,
    store: ArtifactStore,
    register: Any,
    value_column: str,
    group_column: str,
) -> dict:
    val_col = require_numeric(df, value_column)
    grp_col = require_column(df, group_column)

    sub = df[[val_col, grp_col]].dropna()
    caveats: list[str] = []

    counts = sub.groupby(grp_col, observed=True)[val_col].count()
    small = counts[counts < MIN_GROUP_SIZE]
    for group_name in small.index:
        caveats.append(
            f"Group '{group_name}' was excluded: fewer than {MIN_GROUP_SIZE} observations."
        )
    usable_groups = counts[counts >= MIN_GROUP_SIZE].index
    sub = sub[sub[grp_col].isin(usable_groups)]

    counts = sub.groupby(grp_col, observed=True)[val_col].count()
    if len(counts) > MAX_GROUPS:
        total_groups = len(counts)
        top_groups = counts.sort_values(ascending=False).head(MAX_GROUPS).index
        caveats.append(
            f"Limited to the {MAX_GROUPS} largest groups out of {total_groups}; "
            "smaller groups were excluded."
        )
        sub = sub[sub[grp_col].isin(top_groups)]

    n_total = len(sub)
    grouped = sub.groupby(grp_col, observed=True)[val_col]
    n_groups = grouped.ngroups

    if n_groups < 2 or n_total < MIN_OVERALL_N:
        raise ToolError(
            f"Not enough usable data to compare groups of '{grp_col}': {n_groups} usable "
            f"groups, {n_total} total observations. Need at least 2 groups with "
            f"{MIN_GROUP_SIZE}+ observations each and {MIN_OVERALL_N}+ observations overall."
        )

    group_names = list(grouped.groups.keys())
    group_values = [grouped.get_group(g).to_numpy() for g in group_names]
    groups_summary = [
        {"group": str(g), "n": int(len(v)), "mean": num(v.mean())}
        for g, v in zip(group_names, group_values, strict=True)
    ]

    hypothesis = f"H0: mean {val_col} is equal across groups of {grp_col}"
    reading = "p < 0.05 means the groups differ."

    if n_groups == 2:
        a, b = group_values
        t_stat, t_p = stats.ttest_ind(a, b, equal_var=False)
        n1, n2 = len(a), len(b)
        var1, var2 = a.var(ddof=1), b.var(ddof=1)
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        cohens_d = (a.mean() - b.mean()) / pooled_std if pooled_std else float("nan")

        parametric_id = register(
            name="Welch's t-test",
            columns=[val_col, grp_col],
            hypothesis=hypothesis,
            statistic=t_stat,
            p_value=t_p,
            effect_size=cohens_d,
            effect_size_name="cohens_d",
            caveats=caveats,
        )

        u_stat, u_p = stats.mannwhitneyu(a, b)
        nonparametric_id = register(
            name="Mann-Whitney U test",
            columns=[val_col, grp_col],
            hypothesis=hypothesis,
            statistic=u_stat,
            p_value=u_p,
            effect_size=None,
            effect_size_name=None,
            caveats=caveats,
        )

        return {
            "parametric_test_id": parametric_id,
            "nonparametric_test_id": nonparametric_id,
            "groups": groups_summary,
            "t_statistic": num(t_stat),
            "t_p_value": num(t_p),
            "cohens_d": num(cohens_d),
            "u_statistic": num(u_stat),
            "u_p_value": num(u_p),
            "n": n_total,
            "hypothesis": hypothesis,
            "reading": reading,
            "caveats": caveats,
        }

    # 3+ groups: ANOVA + Kruskal-Wallis
    f_stat, f_p = stats.f_oneway(*group_values)
    all_values = np.concatenate(group_values)
    grand_mean = all_values.mean()
    ss_total = float(((all_values - grand_mean) ** 2).sum())
    ss_between = float(sum(len(v) * (v.mean() - grand_mean) ** 2 for v in group_values))
    eta_squared = ss_between / ss_total if ss_total else float("nan")

    parametric_id = register(
        name="One-way ANOVA",
        columns=[val_col, grp_col],
        hypothesis=hypothesis,
        statistic=f_stat,
        p_value=f_p,
        effect_size=eta_squared,
        effect_size_name="eta_squared",
        caveats=caveats,
    )

    h_stat, h_p = stats.kruskal(*group_values)
    nonparametric_id = register(
        name="Kruskal-Wallis test",
        columns=[val_col, grp_col],
        hypothesis=hypothesis,
        statistic=h_stat,
        p_value=h_p,
        effect_size=None,
        effect_size_name=None,
        caveats=caveats,
    )

    return {
        "parametric_test_id": parametric_id,
        "nonparametric_test_id": nonparametric_id,
        "groups": groups_summary,
        "f_statistic": num(f_stat),
        "f_p_value": num(f_p),
        "eta_squared": num(eta_squared),
        "h_statistic": num(h_stat),
        "h_p_value": num(h_p),
        "n": n_total,
        "hypothesis": hypothesis,
        "reading": reading,
        "caveats": caveats,
    }


def _correlation_test(
    df: pd.DataFrame,
    store: ArtifactStore,
    register: Any,
    column_a: str,
    column_b: str,
) -> dict:
    col_a = require_numeric(df, column_a)
    col_b = require_numeric(df, column_b)
    sub = df[[col_a, col_b]].dropna()
    n = len(sub)
    if n < MIN_OVERALL_N:
        raise ToolError(
            f"Not enough paired data to correlate '{col_a}' and '{col_b}': {n} rows, "
            f"need at least {MIN_OVERALL_N}."
        )

    pearson_r, pearson_p = stats.pearsonr(sub[col_a], sub[col_b])
    spearman_rho, spearman_p = stats.spearmanr(sub[col_a], sub[col_b])

    hypothesis = f"H0: no monotonic/linear association between {col_a} and {col_b}"
    reading = "p < 0.05 means the association is unlikely to be due to chance."

    pearson_id = register(
        name="Pearson correlation",
        columns=[col_a, col_b],
        hypothesis=hypothesis,
        statistic=pearson_r,
        p_value=pearson_p,
        effect_size=pearson_r,
        effect_size_name="r",
    )
    spearman_id = register(
        name="Spearman correlation",
        columns=[col_a, col_b],
        hypothesis=hypothesis,
        statistic=spearman_rho,
        p_value=spearman_p,
        effect_size=spearman_rho,
        effect_size_name="rho",
    )

    return {
        "pearson_test_id": pearson_id,
        "spearman_test_id": spearman_id,
        "pearson_r": num(pearson_r),
        "pearson_p": num(pearson_p),
        "spearman_rho": num(spearman_rho),
        "spearman_p": num(spearman_p),
        "n": n,
        "hypothesis": hypothesis,
        "reading": reading,
    }


def _chi_square_test(
    df: pd.DataFrame,
    store: ArtifactStore,
    register: Any,
    column_a: str,
    column_b: str,
) -> dict:
    col_a = require_column(df, column_a)
    col_b = require_column(df, column_b)
    sub = df[[col_a, col_b]].dropna()

    caveats: list[str] = []
    for col in (col_a, col_b):
        top = sub[col].value_counts()
        if len(top) > MAX_CATEGORIES:
            keep = set(top.head(MAX_CATEGORIES).index)
            sub = sub[sub[col].isin(keep)]
            caveats.append(
                f"Column '{col}' has more than {MAX_CATEGORIES} categories; "
                f"limited to the {MAX_CATEGORIES} most frequent."
            )

    n = len(sub)
    table = pd.crosstab(sub[col_a], sub[col_b])
    if table.shape[0] < 2 or table.shape[1] < 2 or n < MIN_OVERALL_N:
        raise ToolError(
            f"Not enough data for a chi-square test between '{col_a}' and '{col_b}': "
            f"contingency table is {table.shape[0]}x{table.shape[1]} with n={n}. "
            "Need at least 2 categories in each column and 8 total observations."
        )

    chi2, p_value, dof, expected = stats.chi2_contingency(table)
    r, c = table.shape
    cramers_v = np.sqrt(chi2 / (n * (min(r, c) - 1))) if min(r, c) > 1 else float("nan")

    if (expected < 5).any():
        caveats.append(
            "Some expected cell counts are below 5; the chi-square approximation may be unreliable."
        )

    hypothesis = f"H0: {col_a} and {col_b} are independent"
    test_id = register(
        name="Chi-square test of independence",
        columns=[col_a, col_b],
        hypothesis=hypothesis,
        statistic=chi2,
        p_value=p_value,
        effect_size=cramers_v,
        effect_size_name="cramers_v",
        caveats=caveats,
    )

    return {
        "test_id": test_id,
        "statistic": num(chi2),
        "p_value": num(p_value),
        "dof": int(dof),
        "cramers_v": num(cramers_v),
        "n": n,
        "table_shape": [r, c],
        "hypothesis": hypothesis,
        "reading": "p < 0.05 means the two columns are associated (not independent).",
        "caveats": caveats,
    }


def _linear_regression(
    df: pd.DataFrame,
    store: ArtifactStore,
    register: Any,
    target: str,
    features: list[str],
) -> dict:
    target_col = require_numeric(df, target)
    caveats: list[str] = []

    requested_features = list(dict.fromkeys(features))
    if len(requested_features) > 8:
        caveats.append(f"Limited to the first 8 of {len(requested_features)} requested features.")
        requested_features = requested_features[:8]

    feature_cols = [require_numeric(df, f) for f in requested_features]

    sub = df[[target_col, *feature_cols]].dropna()

    dropped_constant = []
    usable_features = []
    for col in feature_cols:
        if sub[col].nunique() <= 1:
            dropped_constant.append(col)
        else:
            usable_features.append(col)
    if dropped_constant:
        caveats.append(
            f"Dropped constant (zero-variance) feature(s): {', '.join(dropped_constant)}."
        )

    if not usable_features:
        raise ToolError(
            "No usable features remain after dropping constant columns; "
            "choose at least one non-constant numeric feature."
        )

    sub = sub[[target_col, *usable_features]].dropna()
    n = len(sub)
    k = len(usable_features)
    min_n = max(MIN_OVERALL_N, k + 3)
    if n < min_n:
        raise ToolError(
            f"Not enough complete rows to fit a regression with {k} feature(s): {n} rows, "
            f"need at least {min_n}. Use fewer features or check for missing data."
        )

    y = sub[target_col].to_numpy(dtype=float)
    X_features = sub[usable_features].to_numpy(dtype=float)
    X = np.column_stack([np.ones(n), X_features])

    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ beta
    residuals = y - y_hat
    sse = float((residuals**2).sum())
    sst = float(((y - y.mean()) ** 2).sum())
    r_squared = 1 - sse / sst if sst else float("nan")
    denom = n - k - 1
    adjusted_r_squared = 1 - (1 - r_squared) * (n - 1) / denom if denom > 0 else float("nan")

    sigma2 = sse / denom if denom > 0 else float("nan")
    cov = sigma2 * np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    with np.errstate(divide="ignore", invalid="ignore"):
        t_values = beta / se
    p_values = 2 * stats.t.sf(np.abs(t_values), df=denom) if denom > 0 else np.full(k + 1, np.nan)

    if denom > 0 and k > 0:
        f_stat = (r_squared / k) / ((1 - r_squared) / denom) if r_squared < 1 else float("inf")
        f_p_value = stats.f.sf(f_stat, k, denom)
    else:
        f_stat = float("nan")
        f_p_value = float("nan")

    hypothesis = (
        f"H0: none of the features explain variance in {target_col} (all coefficients are zero)"
    )
    test_id = register(
        name="Ordinary least squares regression",
        columns=[target_col, *usable_features],
        hypothesis=hypothesis,
        statistic=f_stat,
        p_value=f_p_value,
        effect_size=r_squared,
        effect_size_name="r_squared",
        caveats=caveats,
    )

    coefficients = [
        {
            "feature": "intercept" if i == 0 else usable_features[i - 1],
            "coef": num(beta[i]),
            "t": num(t_values[i]),
            "p": num(p_values[i]),
        }
        for i in range(k + 1)
    ]

    return {
        "test_id": test_id,
        "r_squared": num(r_squared),
        "adjusted_r_squared": num(adjusted_r_squared),
        "f_statistic": num(f_stat),
        "f_p_value": num(f_p_value),
        "n": n,
        "k": k,
        "coefficients": coefficients,
        "hypothesis": hypothesis,
        "reading": "A low f_p_value (< 0.05) means the model explains significant variance.",
        "caveats": caveats,
    }
