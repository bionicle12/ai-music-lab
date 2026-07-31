from pathlib import Path

from music_lab_ui.contracts import AnalysisRun, DetectorResult
from music_lab_ui.ui_presenters import (
    comparison_metric_rows,
    detector_cards,
    detector_delta_rows,
    history_rows,
)
from music_lab_ui.ui_service import RunComparisonOutcome
from tests.test_comparison import feature_fixture
from music_lab_ui.i18n import get_translator

t = get_translator()


def detector_result(detector: str, probability: float) -> DetectorResult:
    return DetectorResult(
        detector=detector,
        status="ok",
        probability=probability,
        label="Fake" if probability >= 0.5 else "Real",
        confidence=abs(probability - 0.5) * 2,
        runtime_seconds=1.25,
        device="test",
    )


def analysis_run(
    run_id: str,
    filename: str,
    results: tuple[DetectorResult, ...],
    note: str = "",
) -> AnalysisRun:
    return AnalysisRun(
        run_id=run_id,
        created_at="2026-07-30T09:19:40.123456+00:00",
        filename=filename,
        audio_path=Path("input.mp3"),
        features_path=Path("features.npz"),
        result_path=Path("result.json"),
        note=note,
        selected_detectors=tuple(result.detector for result in results),
        results=results,
        is_baseline=False,
    )


def test_fst_lower_boundary_has_generator_shift_warning() -> None:
    rendered = detector_cards((detector_result("FST", 0.011),))

    assert t("caveat.fst.floor") in rendered
    assert "false negative" in rendered


def test_fst_upper_boundary_is_not_presented_as_a_guarantee() -> None:
    rendered = detector_cards((detector_result("FST", 0.989),))

    assert t("caveat.fst.ceiling") in rendered


def test_history_rows_have_duration_and_no_baseline_column() -> None:
    run = analysis_run(
        "20260730T091940-0f6fcc6a78",
        "хрю хрю бля.mp3",
        (
            detector_result("lofcz", 0.999998),
            detector_result("FST", 0.011),
        ),
    )

    rows = history_rows([run], {run.run_id: 52.0})

    assert rows[0] == [
        "2026-07-30 09:19:40",
        "хрю хрю бля.mp3",
        t("detector.seconds", value="52.0"),
        "100.0%",
        "1.1%",
        "",
        run.run_id,
        "",
    ]


def test_history_marks_explicit_version_a() -> None:
    run = analysis_run("a", "original.wav", ())
    run = AnalysisRun(**{**run.__dict__, "is_baseline": True})

    rows = history_rows([run], {run.run_id: 1.0})

    assert rows[0][-1] == "★ A"


def test_detector_delta_rows_use_b_minus_a() -> None:
    run_a = analysis_run(
        "a",
        "a.wav",
        (detector_result("lofcz", 0.2),),
    )
    run_b = analysis_run(
        "b",
        "b.wav",
        (detector_result("lofcz", 0.7),),
    )
    features = feature_fixture()
    outcome = RunComparisonOutcome(
        run_a=run_a,
        run_b=run_b,
        features_a=features,
        features_b=features,
        comparison=None,
        comparison_note=None,
    )

    rows = detector_delta_rows(outcome)

    assert rows[0][0] == "lofcz"
    assert rows[0][3] == f'+50.0 {t("unit.percentage_points")}'


def test_scalar_metric_rows_remain_available_without_heatmap() -> None:
    run_a = analysis_run("a", "a.wav", ())
    run_b = analysis_run("b", "b.wav", ())
    features_a = feature_fixture(duration=100.0)
    features_b = feature_fixture(duration=120.0)
    outcome = RunComparisonOutcome(
        run_a=run_a,
        run_b=run_b,
        features_a=features_a,
        features_b=features_b,
        comparison=None,
        comparison_note="duration differs by more than 5%",
    )

    rows = comparison_metric_rows(outcome)

    assert rows[0][0] == t("meta.duration")
    assert rows[0][1:4] == ["100.00", "120.00", "20.00"]
